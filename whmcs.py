import asyncio
import aiohttp
import aiofiles
from fake_useragent import UserAgent
import sys

ua = UserAgent()

# Common WHMCS markers
WHMCS_SIGNATURES = [
    "Powered by WHMCS",
    "WHMCS",
    "dologin.php",
    "name=\"loginform\"",
    "/clientarea.php"
]

async def check_url(session, url, output_file):
    headers = {
        "User-Agent": ua.random
    }
    try:
        async with session.get(url, headers=headers, timeout=15, allow_redirects=True, ssl=False) as response:
            text = await response.text()
            if any(sig in text for sig in WHMCS_SIGNATURES):
                print(f"[+] Found WHMCS: {url}")
                async with aiofiles.open(output_file, mode='a') as f:
                    await f.write(url + '\n')
            else:
                print(f"[-] Not WHMCS: {url}")
    except Exception as e:
        print(f"[!] Error checking {url}: {e}")

async def main(input_file, output_file="working.txt"):
    urls = []

    # Read and clean URLs
    async with aiofiles.open(input_file, mode='r') as f:
        async for line in f:
            line = line.strip()
            if not line:
                continue

            # Expect format: full_url:username:password
            if "://" in line:
                try:
                    scheme, rest = line.split("://", 1)
                    domain_and_path = rest.split(":", 1)[0]
                    clean_url = f"{scheme}://{domain_and_path}"
                    urls.append(clean_url)
                except Exception:
                    continue

    async with aiohttp.ClientSession() as session:
        tasks = [check_url(session, url, output_file) for url in urls]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 whmcs_checker.py input.txt [output.txt]")
    else:
        input_filename = sys.argv[1]
        output_filename = sys.argv[2] if len(sys.argv) > 2 else "working.txt"
        asyncio.run(main(input_filename, output_filename))
