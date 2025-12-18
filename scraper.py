"""
MCMC Amateur Radio Station Assignments Scraper

Uses Playwright with stealth mode and anti-detection measures to scrape 
call sign data from the MCMC Register of Apparatus Assignments.

Features:
- Checkpoint/resume: Saves progress, can resume from interruption
- Random delays: Human-like pauses between requests
- Session rotation: Creates new browser session every N pages
- Incremental saves: Commits data to DB after each page
"""
import asyncio
import argparse
import random
from playwright.async_api import async_playwright
from database import (
    init_database, clear_assignments, upsert_assignments_batch,
    get_assignment_count, start_scrape_session, update_scrape_session,
    complete_scrape_session, save_checkpoint, get_checkpoint, clear_checkpoint
)

# Constants
BASE_URL = "https://www.mcmc.gov.my/en/legal/registers/register-of-apparatus-assignments-search"
APPARATUS_TYPE = "AARadio"  # Amateur Radio Station

# Anti-detection settings
MIN_DELAY = 2.0       # Minimum delay between pages (seconds)
MAX_DELAY = 5.0       # Maximum delay between pages (seconds)
LONG_BREAK_EVERY = 50  # Take a longer break every N pages
LONG_BREAK_MIN = 30   # Minimum long break duration (seconds)
LONG_BREAK_MAX = 60   # Maximum long break duration (seconds)
SESSION_ROTATE_EVERY = 10000  # Disabled - use checkpoint/resume instead after interruption
SAVE_CHECKPOINT_EVERY = 5   # Save checkpoint every N pages


async def create_stealth_context(playwright):
    """Create a browser context with stealth settings."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ]
    )
    
    # Randomize viewport slightly
    width = random.randint(1800, 1920)
    height = random.randint(900, 1080)
    
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': width, 'height': height},
        locale='en-US',
        timezone_id='Asia/Kuala_Lumpur',
    )
    
    # Anti-detection scripts
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'ms'] });
        window.chrome = { runtime: {} };
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)
    
    return browser, context


async def random_delay(page_num):
    """Add random delay, with longer breaks periodically."""
    if page_num > 0 and page_num % LONG_BREAK_EVERY == 0:
        delay = random.uniform(LONG_BREAK_MIN, LONG_BREAK_MAX)
        print(f"  Taking a longer break: {delay:.1f}s")
    else:
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
    await asyncio.sleep(delay)


async def extract_table_data(page):
    """Extract table data from current page using JavaScript."""
    table_data = await page.evaluate("""
        () => {
            const results = [];
            const tables = document.querySelectorAll('table');
            
            tables.forEach((table) => {
                const rows = table.querySelectorAll('tr');
                rows.forEach((row) => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 5) {
                        const rowData = {
                            rowNum: cells[0]?.textContent?.trim() || '',
                            holder: cells[1]?.textContent?.trim() || '',
                            callSign: cells[2]?.textContent?.trim() || '',
                            assignNo: cells[3]?.textContent?.trim() || '',
                            expiry: cells[4]?.textContent?.trim() || ''
                        };
                        if (rowData.rowNum && rowData.callSign) {
                            results.push(rowData);
                        }
                    }
                });
            });
            
            return results;
        }
    """)
    return table_data


async def click_next_page(page):
    """Click next page link if available. Returns True if successful."""
    result = await page.evaluate("""
        () => {
            const nextLinks = document.querySelectorAll('a');
            for (const link of nextLinks) {
                const text = link.textContent.trim().toLowerCase();
                if (text === 'next' || text === '>' || text === '»' || text === 'next page') {
                    link.click();
                    return true;
                }
            }
            
            const paginationArea = document.querySelector('.pagination, .pager, [class*="paging"]');
            if (paginationArea) {
                const links = paginationArea.querySelectorAll('a');
                let foundCurrent = false;
                for (const link of links) {
                    if (foundCurrent) {
                        link.click();
                        return true;
                    }
                    if (link.parentElement?.classList?.contains('active') || 
                        link.classList?.contains('active')) {
                        foundCurrent = true;
                    }
                }
            }
            
            return false;
        }
    """)
    return result


async def navigate_to_page(page, target_page):
    """Navigate to a specific page number using pagination."""
    print(f"  Navigating to page {target_page}...")
    
    # Try direct page link first
    clicked = await page.evaluate(f"""
        (targetPage) => {{
            const links = document.querySelectorAll('a');
            for (const link of links) {{
                if (link.textContent.trim() === String(targetPage)) {{
                    link.click();
                    return true;
                }}
            }}
            return false;
        }}
    """, target_page)
    
    if clicked:
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        return True
    
    return False


async def scrape_with_session(playwright, start_page, session_id, total_added, total_updated, total_records):
    """Scrape pages with a single browser session. Returns updated counts and last page."""
    browser, context = await create_stealth_context(playwright)
    page = await context.new_page()
    
    try:
        # Navigate to initial URL
        url = f"{BASE_URL}?type={APPARATUS_TYPE}"
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(3)
        
        title = await page.title()
        print(f"Page title: {title}")
        
        # Check for Cloudflare
        if "Cloudflare" in title or "Attention" in title:
            print("Cloudflare detected, waiting...")
            await asyncio.sleep(15)
            title = await page.title()
            print(f"Title after wait: {title}")
            if "Cloudflare" in title:
                raise Exception("Could not bypass Cloudflare")
        
        # Click Search button to trigger full search
        print("Clicking Search button to load full dataset...")
        clicked = await page.evaluate("""
            () => {
                const btn = document.querySelector("input[value='Search']");
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            }
        """)
        if clicked:
            print("Search triggered, waiting for results...")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
        else:
            print("Search button not found, using default results")
        
        # If resuming, navigate to the start page by clicking through
        if start_page > 1:
            print(f"Resuming from page {start_page} - navigating through {start_page - 1} pages...")
            current_page = 1
            while current_page < start_page:
                if await click_next_page(page):
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1)  # Quick navigation, no long delays
                    current_page += 1
                    if current_page % 10 == 0:
                        print(f"  Navigated to page {current_page}...")
                else:
                    print(f"  Could not navigate beyond page {current_page}")
                    break
            print(f"  Reached page {current_page}")
        
        page_num = start_page
        pages_in_session = 0
        max_pages = 1000
        consecutive_no_new = 0  # Track pages with no new records
        
        while page_num <= max_pages:
            pages_in_session += 1
            
            # Check if we need to rotate session
            if pages_in_session > SESSION_ROTATE_EVERY:
                print(f"\n=== Session rotation at page {page_num} ===")
                save_checkpoint(session_id, page_num, total_records)
                return page_num, total_added, total_updated, total_records, "rotate"
            
            print(f"\n--- Page {page_num} ---")
            
            # Extract data
            table_data = await extract_table_data(page)
            
            if not table_data:
                print("No data found on this page")
                # Check if we're on a Cloudflare page
                title = await page.title()
                if "Cloudflare" in title:
                    print("Hit Cloudflare block!")
                    save_checkpoint(session_id, page_num, total_records)
                    return page_num, total_added, total_updated, total_records, "blocked"
                break
            
            # Process data
            page_assignments = []
            for row in table_data:
                if row['rowNum'].isdigit() and row['callSign'] and row['holder']:
                    page_assignments.append((
                        int(row['rowNum']),
                        row['holder'],
                        row['callSign'],
                        row['assignNo'],
                        row['expiry']
                    ))
            
            if not page_assignments:
                print("No valid assignments found, stopping")
                break
            
            # Save immediately to database
            added, updated = upsert_assignments_batch(page_assignments)
            total_added += added
            total_updated += updated
            total_records += len(page_assignments)
            
            print(f"Page {page_num}: {len(page_assignments)} records ({added} new, {updated} updated)")
            print(f"  Running total: {total_records} scraped, {get_assignment_count()} in DB")
            
            # Duplicate detection - stop if no new records for 10 consecutive pages
            if added == 0:
                consecutive_no_new += 1
                if consecutive_no_new >= 10:
                    print(f"\nNo new records for {consecutive_no_new} consecutive pages, stopping.")
                    break
            else:
                consecutive_no_new = 0  # Reset counter
            
            # Update session progress
            update_scrape_session(session_id, total_records, total_added, total_updated, page_num)
            
            # Save checkpoint periodically
            if page_num % SAVE_CHECKPOINT_EVERY == 0:
                save_checkpoint(session_id, page_num, total_records)
                print(f"  Checkpoint saved at page {page_num}")
            
            # Try to go to next page
            if await click_next_page(page):
                await page.wait_for_load_state("networkidle")
                await random_delay(page_num)
                page_num += 1
            else:
                print("No next page found, finished!")
                break
        
        return page_num, total_added, total_updated, total_records, "completed"
        
    finally:
        await context.close()
        await browser.close()


async def scrape_all(fresh=False, resume=False):
    """Main scraping function with session rotation and resume support."""
    print("=" * 60)
    print("MCMC Amateur Radio Station Assignments Scraper")
    print(f"Mode: {'FRESH' if fresh else 'INCREMENTAL'} | Resume: {resume}")
    print("=" * 60)
    
    init_database()
    
    start_page = 1
    total_added = 0
    total_updated = 0
    total_records = 0
    
    if fresh:
        clear_assignments()
        session_id = start_scrape_session()
    else:
        # Auto-resume from checkpoint if exists (--resume flag is now optional)
        checkpoint = get_checkpoint()
        if checkpoint:
            session_id, start_page, total_records = checkpoint
            start_page += 1  # Resume from next page
            print(f"Auto-resuming from checkpoint: page {start_page}, {total_records} records scraped")
        else:
            session_id = start_scrape_session()
    
    async with async_playwright() as p:
        current_page = start_page
        status = "running"
        
        while status not in ["completed", "blocked"]:
            print(f"\n{'=' * 40}")
            print(f"Starting session from page {current_page}")
            print(f"{'=' * 40}")
            
            try:
                current_page, total_added, total_updated, total_records, status = await scrape_with_session(
                    p, current_page, session_id, total_added, total_updated, total_records
                )
                
                if status == "rotate":
                    print(f"\nSession rotation - taking a break before continuing...")
                    await asyncio.sleep(random.uniform(LONG_BREAK_MIN, LONG_BREAK_MAX))
                    status = "running"
                elif status == "blocked":
                    print(f"\nBlocked by Cloudflare at page {current_page}")
                    print("Waiting 5 minutes before retry...")
                    await asyncio.sleep(300)  # Wait 5 minutes
                    status = "running"  # Try again
                    
            except Exception as e:
                print(f"\nError at page {current_page}: {e}")
                save_checkpoint(session_id, current_page, total_records)
                complete_scrape_session(
                    session_id, total_records, total_added, total_updated, current_page, "failed"
                )
                raise
    
    # Clear checkpoint on successful completion
    clear_checkpoint()
    
    complete_scrape_session(
        session_id, total_records, total_added, total_updated, current_page, "completed"
    )
    
    print("\n" + "=" * 60)
    print("Scraping complete!")
    print(f"  Pages scraped: {current_page}")
    print(f"  Records found: {total_records}")
    print(f"  New records: {total_added}")
    print(f"  Updated records: {total_updated}")
    print(f"  Total in database: {get_assignment_count()}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape MCMC Amateur Radio Station assignments"
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Clear database and perform fresh scrape"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint if available"
    )
    args = parser.parse_args()
    
    asyncio.run(scrape_all(fresh=args.fresh, resume=args.resume))


if __name__ == "__main__":
    main()
