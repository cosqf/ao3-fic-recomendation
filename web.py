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