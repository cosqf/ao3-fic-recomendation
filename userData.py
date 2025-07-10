import pandas as pd 

def processWork(work, rows):
    if "deleted" in work.get_attribute("class"): 
        return
    
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

    last_visited = work.locator ("div.user.module.group h4.viewed.heading").inner_text().split(" ")[2:5]
    last_visited = ' '.join (last_visited)
    parsed_date = pd.to_datetime(last_visited, format="%d %b %Y")
    
    bookmark = False
    rows.append([id, rating, orientations, fandoms, ships, tags, words, parsed_date, bookmark])