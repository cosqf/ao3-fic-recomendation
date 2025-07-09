import time
from playwright.sync_api import Playwright, sync_playwright, TimeoutError
from userData import processWork
import pandas as pd
import random

def settingUpBrowser (pw: Playwright):
        agent = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
        browser = pw.chromium.launch(headless=True).new_context(user_agent=agent)
        return browser.new_page()

def logIn(user, pwd, page):
    login_url = "https://archiveofourown.org/users/login"
    try:
        print ("getting on the website")
        page.goto(login_url)

        page.fill("#user_login", user)
        page.fill("#user_password", pwd)

        print ("logging in...")

        page.locator ("#new_user > dl > dd.submit.actions > input").click()
       
        error_alert = page.locator(".flash.alert")
        if error_alert.count() > 0 and error_alert.is_visible():
            print("login failed!", error_alert.inner_text())
            time.sleep(5)
            page.close()
            exit()
             
        error_flash = page.locator(".flash.error")
        if error_flash.count() > 0 and error_flash.is_visible():
            print("login failed!", error_flash.inner_text())
            time.sleep(5)
            page.close()
            exit()

        page.wait_for_selector("#dashboard") 

        print(f"login successful! current url: {page.url}")
        return page  
                
    except Exception as e:
        print(f"Error: {e}")
        exit()


def gettingHistory (page, username, dataFrame):
    link_base = f"https://archiveofourown.org/users/{username}/readings?page="
    print("Navigating to the history page...")
    page.goto(link_base + "1")

    print("Getting ready to read the history...")

    page.wait_for_selector(".pagination.actions.pagy")

    pagination_items = page.locator(".pagination.actions.pagy li")
    count = pagination_items.count()
    if count < 3:
        print("error reading history page")
        exit()

    last_page = int (pagination_items.nth(count - 2).inner_text())
    print("total pages:", last_page)
    print("starting to read")

    for p in range(1, last_page + 1):
        full_url = link_base + str(p)
        # time.sleep(random.uniform(5, 10)) 
        page.goto(full_url)

        page.wait_for_selector("#main > ol.reading.work.index.group")
        work_list = page.locator("li[role='article']")
        count = work_list.count()
        rows = []
        for i in range (count):
            work = work_list.nth (i)
            processWork (work, rows)

        new_rows = pd.DataFrame(rows, columns = ["fic_id", "rating", "orientations" ,"fandom", "ships", "tags",  "word_count", "last_visited", "bookmarked"])
        dataFrame = pd.concat ([dataFrame, new_rows], ignore_index = True)

        print(f"Page {p} read")

    print("reading finished")
    return dataFrame


def checkBookmarks (username, dataframe : pd.DataFrame, page):
    print ("checking bookmarks")
    base_url = f"https://archiveofourown.org/users/{username}/bookmarks?page="
    pageNumber = 1
    while True:
        url = base_url + str(pageNumber)
        page.goto(url)
        
        work_list = page.locator("li[role='article']")
        count = work_list.count()
        
        for i in range (count):
            work = work_list.nth (i)
            if "deleted" in work.get_attribute("class"): 
                continue
            id = int(work.locator("h4.heading a[href^='/works/']").get_attribute("href")[7:])
            dataframe.loc[dataframe["fic_id"] == id, "bookmarked"] = True
            

        # check if has seen all pages 
        numberUsersHeader = page.locator("#main > h2").text_content()
        if numberUsersHeader:
            if len(numberUsersHeader.split("-")) == 1: #only one page to check
                page.close()
                break
            numberKudos = numberUsersHeader.split("-")[1].split(" ")
        else:
            print ("error reading page")
            break
        
        if (int (numberKudos[1].replace(",", "")) >= int (numberKudos[3].replace(",", ""))): # reached the end
            page.close()
            break

        print(f"Page {pageNumber} of bookmarks read")
        pageNumber +=1
        




def checkKudo (username, work, pw): # too heavy, not in use
    workSubUrl = work.locator("h4.heading a[href^='/works/']").get_attribute("href")
    if workSubUrl is None:
        print ("error reading page")
        return False
    
    url = f"https://archiveofourown.org{workSubUrl}/kudos?page="
    pageNumber = 1

    page = settingUpBrowser(pw)
    while (True):
        current_url = url + str(pageNumber)
        for attempt in range (3):
            try:
                page.goto(current_url, timeout=5000)
                
                # check for "Retry Later"
                page_content = page.content()
                if "retry later" in page_content.lower() or "too many requests" in page_content.lower():
                    if attempt <2:
                        print(f"detected 'Retry Later' message on {current_url}. Waiting longer and retrying...")
                        time.sleep(random.uniform(120, 180)) # a longer, forced wait
                        continue
                    else:
                        print(f"Max retries reached due to 'Retry Later' error: {current_url}. Giving up on this page.")
                        page.close()
                        return False

                page.wait_for_selector("p.kudos", timeout=5000) #ensuring the page loaded
                break

            except Exception as e:
                print(f"An unexpected error occurred on attempt {attempt + 1}/3 for page {current_url}: {e}. Retrying...")
                if attempt < 2:
                    time.sleep(2) 
                else:
                    print(f"Max retries reached due to error {e}, for page: {current_url}. Giving up on this page.")
                    page.close()
                    return False
        usernamesRaw = page.locator("p.kudos").text_content()
        if (usernamesRaw):
            usernames = [name.strip() for name in usernamesRaw.split(",")]
        else:
            print ("error reading page")
            return False
        if username in usernames: #found user, kudo!
            page.close()
            print (f"{workSubUrl} was kudoed")
            return True
        
        # check if has seen all pages 
        numberUsersHeader = page.locator("#main.kudos-index h2.heading").text_content()
        if numberUsersHeader:
            if len(numberUsersHeader.split("-")) == 1: #only one page of kudos to check
                page.close()
                print (f"{workSubUrl} wasn't kudoed")
                return False
            numberKudos = numberUsersHeader.split("-")[1].split(" ")
        else:
            print ("error reading page")
            return False
        
        if (int (numberKudos[1].replace(",", "")) >= int (numberKudos[3].replace(",", ""))): # reached the end, didnt find the user
            page.close()
            print (f"{workSubUrl} wasn't kudoed")
            return False
        
        pageNumber += 1

                
        
