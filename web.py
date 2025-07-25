import time
from playwright.sync_api import Playwright
import pandas as pd
import re
from urllib.parse import quote_plus

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


def gettingHistory(page, username, dataFrame):
    link_base = f"https://archiveofourown.org/users/{username}/readings?page="
    
    print("Getting ready to read the history...")

    scraped_history_fics = scrape_works(
        page,
        link_base,
        pagination_selector=".pagination.actions.pagy",
        work_list_selector="#main > ol.reading.work.index.group", 
        is_processing_history=True
    )

    dataFrame = pd.concat([dataFrame, scraped_history_fics], ignore_index=True)
    
    print("reading finished")
    return dataFrame



def scrape_works(page, base_url_full_query, pagination_selector, work_list_selector, is_processing_history, history_df=None, max_number_works = None):
    all_processed_rows = []
    stored_num_works = 0
    print(f"Navigating to the first page: {base_url_full_query}1")
    page.goto(base_url_full_query + "1")
    page.wait_for_selector("h2.heading")

    pagination_locator = page.locator(pagination_selector)
    pagination_exists = pagination_locator.count() > 0

    last_page = 1 # default to 1 page

    if pagination_exists:
        pagination_items = pagination_locator.locator("li")
        count = pagination_items.count()
        if count < 3:
            print("pagination items are less than 3, assuming 1 page")
            last_page = 1
        else:
            try:
                last_page = int(pagination_items.nth(count - 2).inner_text().strip())
            except ValueError:
                print("could not parse last page number, assuming 1 page")
                last_page = 1
    else:
        print("no pagination found, assuming 1 page.")

    print("total pages to read: ", last_page)
    print("starting to read")

    for p in range(1, last_page + 1):
        current_page_url = base_url_full_query + str(p)
        page.goto(current_page_url)
        page.wait_for_selector("h2.heading")

        works_main_container = page.locator(work_list_selector)
        if works_main_container.count() < 1:
            print(f"No works found on page {p}, skipping...")
            continue # page might be empty or error

        work_list = page.locator("li[role='article']") 
        work_count_on_page = work_list.count()
        if work_count_on_page == 0:
            print(f"No works found on page {p}, skipping...")
            continue # filter too intense or no results

        print(f"processing {work_count_on_page} works on page {p}")
        rows_on_page = []
        for i in range(work_count_on_page):
            work = work_list.nth(i)
            try:
                processed_work = processWork(work, is_processing_history)
                # logic for unread fics: check if already in history
                if history_df is not None and (history_df['fic_id'] == processed_work[0]).any():
                    continue
                rows_on_page.append(processed_work)
                stored_num_works += 1
            except Exception as e:
                print(f"Error processing work {i+1} on page {p}: {e}. Waiting and skipping...")
                time.sleep(30) 
                continue

            if max_number_works is not None and stored_num_works >= max_number_works:
                break
        all_processed_rows.append(pd.DataFrame(rows_on_page, columns=["fic_id", "rating", "orientations", "fandom", "ships", "tags", "word_count", "last_visited", "bookmarked"]))
        

        if max_number_works is not None and stored_num_works >= max_number_works:
            break
    if all_processed_rows:
        return pd.concat(all_processed_rows, ignore_index=True)
    else:
        return pd.DataFrame(columns=["fic_id", "rating", "orientations", "fandom", "ships", "tags", "word_count", "last_visited", "bookmarked"])



def processWork(work, is_history : bool):
    if "deleted" in work.get_attribute("class"): 
        return []
    
    work_link_locator = work.locator("h4.heading a[href^='/works/']")
    work_link_locator.wait_for(state="attached", timeout=15000)

    id = int (work_link_locator.get_attribute("href", timeout=5000)[7:])

    all_ships = work.locator("li.relationships").all()
    ships = [ship.locator("a.tag").inner_text().strip() for ship in all_ships]

    rating = work.locator("ul.required-tags li").nth(0).inner_text().strip()

    orientations = [o.inner_text().strip() for o in work.locator("ul.required-tags li").nth(2).all()]

    all_tags = work.locator("li.freeforms").all()
    tags = [tag.locator("a.tag").inner_text().strip() for tag in all_tags]

    fandoms = [f.inner_text().strip() for f in work.locator("h5.fandoms.heading a.tag").all()]
    fandoms.sort()
    
    # rounds word count to the nearest 1000 multiple 
    words_tag = work.locator("dd.words")
    words_text = words_tag.inner_text().replace(",", "") if words_tag.count() > 0 else "0"
    words = int(words_text)
    words = round(words / 1000) * 1000 if (words > 1000) else 1000

    if is_history:
        last_visited = work.locator ("div.user.module.group h4.viewed.heading").inner_text().split(" ")[2:5]
        last_visited = ' '.join (last_visited)
        parsed_date = pd.to_datetime(last_visited, format="%d %b %Y")
    else:
        parsed_date = None

    bookmark = False
    return [id, rating, orientations, fandoms, ships, tags, words, parsed_date, bookmark]



def scrap_unread_fics(page, history_df, tag_ship_counts, ship_tag):
    max_number_fics = 200
    base_search_url = 'https://archiveofourown.org/works/search?'
    number_tags = 5

    tags = tag_ship_counts['tag'].head(number_tags).tolist()
    formatted_tags = [quote_plus(t) for t in tags]
    
    formatted_ship_tag = re.sub(r"\([^)]*\)", "", ship_tag).strip()
    formatted_ship_tag = quote_plus(formatted_ship_tag)

    unread_df = pd.DataFrame(columns=["fic_id", "rating", "orientations", "fandom", "ships", "tags", "word_count", "last_visited", "bookmarked"])

    while unread_df.shape[0] < max_number_fics and number_tags >= 0:
        current_url_query = f"work_search%5Brelationship_names%5D={formatted_ship_tag}&work_search%5Bfreeform_names%5D="
        
        for t in range(number_tags):
            current_url_query = f"{current_url_query}%2C{formatted_tags[t]}"

        current_url_query += "&work_search%5Bsort_column%5D=kudos_count&commit=Search&page="
        full_base_url = base_search_url + current_url_query

        print(f"searching with {number_tags} tags")

        newly_scraped_fics = scrape_works(
            page,
            full_base_url,
            pagination_selector = "ol.pagination.actions",
            work_list_selector = "#main > ol.work.index.group",
            is_processing_history = False, 
            history_df = pd.concat([history_df, unread_df]),
            max_number_works = 100 if number_tags > 0 else max_number_fics - unread_df.shape[0]
        )
        newly_scraped_fics.drop_duplicates(subset=['fic_id'], inplace=True)
        existing_fic_ids = unread_df['fic_id'].unique()
        newly_scraped_fics = newly_scraped_fics[~newly_scraped_fics['fic_id'].isin(existing_fic_ids)]

        unread_df = pd.concat([unread_df, newly_scraped_fics], ignore_index=True)
        print(f"currently have {unread_df.shape[0]} unread fics stored\n")

        number_tags -= 1 

    print(f"Finished getting unread fics, with {unread_df.shape[0]} fics")
    return unread_df

            
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



#basic url
# https://archiveofourown.org/works/search?


# relationship tags (separated by %2C)
# work_search%5Brelationship_names%5D=Noelle+Holiday%2FSusie
# work_search%5Brelationship_names%5D=noelle+holiday%2Fsusie%2Ckris%2Fsusie+%28deltarune%29&

# add tags (separated by %2C)
# &work_search%5Bfreeform_names%5D=fluff%2Cnonbinary+kris

# sort by kudos:
# &work_search%5Bsort_column%5D=kudos_count&commit=Search

# no tag:
# https://archiveofourown.org/works?commit=Sort+and+Filter&work_search%5Bsort_column%5D=kudos_count&work_search%5Bother_tag_names%5D=&work_search%5Bexcluded_tag_names%5D=&work_search%5Bcrossover%5D=&work_search%5Bcomplete%5D=&work_search%5Bwords_from%5D=&work_search%5Bwords_to%5D=&work_search%5Bdate_from%5D=&work_search%5Bdate_to%5D=&work_search%5Bquery%5D=&work_search%5Blanguage_id%5D=&tag_id=Noelle+Holiday*s*Susie
# with tag:
# https://archiveofourown.org/works?commit=Sort+and+Filter&work_search%5Bsort_column%5D=kudos_count&include_work_search%5Bfreeform_ids%5D%5B%5D=27174440&work_search%5Bother_tag_names%5D=&work_search%5Bexcluded_tag_names%5D=&work_search%5Bcrossover%5D=&work_search%5Bcomplete%5D=&work_search%5Bwords_from%5D=&work_search%5Bwords_to%5D=&work_search%5Bdate_from%5D=&work_search%5Bdate_to%5D=&work_search%5Bquery%5D=&work_search%5Blanguage_id%5D=&tag_id=Noelle+Holiday*s*Susie

# &tag_id=Nonbinary+Kris+%28Deltarune%29
# &include_work_search%5Bfreeform_ids%5D%5B%5D=27174440

# https://archiveofourown.org/works/search?work_search%5Brelationship_names%5D=Noelle+Holiday%2FSusie&work_search%5Bfreeform_names%5D=fluff%2Cnonbinary+kris&work_search%5Bsort_column%5D=kudos_count&commit=Search
# https://archiveofourown.org/works/search?work_search%5Brelationship_names%5D=noelle+holiday%2Fsusie%2Ckris%2Fsusie+%28deltarune%29&work_search%5Bfreeform_names%5D=fluff%2Cnonbinary+kris&work_search%5Bhits%5D=&work_search%5Bkudos_count%5D=&work_search%5Bcomments_count%5D=&work_search%5Bbookmarks_count%5D=&work_search%5Bsort_column%5D=kudos_count&work_search%5Bsort_direction%5D=desc
# https://archiveofourown.org/works/search?work_search%5Brelationship_names%5D=Noelle+Holiday%2FSusie+%28Deltarune%29&work_search%5Bfreeform_names%5D=Nonbinary+Kris+%28Deltarune%29&work_search%5Bsort_column%5D=kudos_count&commit=Search
# https://archiveofourown.org/works?commit=Sort+and+Filter&include_work_search%5Bfreeform_ids%5D%5B%5D=27174440&tag_id=Noelle+Holiday*s*Susie