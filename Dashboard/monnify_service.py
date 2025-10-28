import requests
import base64
import logging
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MonnifyService:
    """Fixed Monnify API integration service"""
    
    def __init__(self):
        self.api_key = settings.MONNIFY_API_KEY
        self.secret_key = settings.MONNIFY_SECRET_KEY
        self.contract_code = settings.MONNIFY_CONTRACT_CODE
        self.base_url = settings.MONNIFY_BASE_URL.rstrip('/')
        self.access_token = None
    
    def _get_auth_header(self):
        """Generate Basic Auth header for login"""
        credentials = f"{self.api_key}:{self.secret_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    def authenticate(self):
        """
        Authenticate with Monnify and get access token
        Token cached for 11 hours (Monnify tokens last 12 hours)
        """
        cached_token = cache.get('monnify_access_token')
        if cached_token:
            self.access_token = cached_token
            logger.debug("Using cached Monnify token")
            return True
        
        try:
            url = f"{self.base_url}/api/v1/auth/login"
            headers = {
                "Authorization": self._get_auth_header(),
                "Content-Type": "application/json"
            }
            
            logger.info(f"Authenticating with Monnify: {url}")
            response = requests.post(url, headers=headers, timeout=30)
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('requestSuccessful'):
                self.access_token = data['responseBody']['accessToken']
                cache.set('monnify_access_token', self.access_token, 39600)  # 11 hours
                logger.info("Monnify authentication successful")
                return True
            else:
                error_msg = data.get('responseMessage', 'Unknown error')
                logger.error(f"Monnify auth failed: {error_msg}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Monnify authentication error: {str(e)}")
            return False
    
    def _make_request(self, method, endpoint, data=None, params=None):
        """Make authenticated request to Monnify API with retry on 401"""
        if not self.access_token:
            if not self.authenticate():
                logger.error("Failed to authenticate")
                return None
        
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            logger.debug(f"{method} {url}")
            
            kwargs = {'headers': headers, 'timeout': 30}
            if data:
                kwargs['json'] = data
            if params:
                kwargs['params'] = params
            
            response = requests.request(method, url, **kwargs)
            
            # Retry on 401 (token expired)
            if response.status_code == 401:
                logger.warning("Token expired, re-authenticating...")
                cache.delete('monnify_access_token')
                self.access_token = None
                if self.authenticate():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    kwargs['headers'] = headers
                    response = requests.request(method, url, **kwargs)
            
            # Handle 503 Service Unavailable separately
            if response.status_code == 503:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('responseMessage', 'Service temporarily unavailable')
                except:
                    error_msg = 'Service temporarily unavailable'
                logger.error(f"Monnify service unavailable (503): {error_msg}")
                return {'error': 'service_unavailable', 'message': error_msg}
            
            response.raise_for_status()
            result = response.json()
            
            logger.debug(f"Response: {result.get('requestSuccessful')} - {result.get('responseMessage')}")
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return {'error': 'timeout', 'message': 'Request timed out'}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            return {'error': 'connection', 'message': 'Connection failed'}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            # Try to parse error response
            try:
                error_data = e.response.json()
                return {'error': 'http_error', 'message': error_data.get('responseMessage', str(e))}
            except:
                return {'error': 'http_error', 'message': str(e)}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            return {'error': 'request_failed', 'message': str(e)}
        except ValueError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return {'error': 'invalid_response', 'message': 'Invalid JSON response'}
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return {'error': 'unknown', 'message': str(e)}
    
    def create_reserved_account(self, user_account, bvn=None, nin=None):
        """
        Create permanent reserved account (Monnify V2 API)
        FIXED: Use getAllAvailableBanks=true as per Monnify support guidance
        """
        try:
            import uuid
            account_reference = f"VA-{user_account.user.username}-{str(uuid.uuid4())[:8]}"
            
            user = user_account.user
            full_name = user.get_full_name() or user.username
            
            # Build payload according to Monnify support guidance
            # CRITICAL: getAllAvailableBanks MUST be true (don't use preferredBanks with it)
            payload = {
                "accountReference": account_reference,
                "accountName": full_name[:50],
                "currencyCode": "NGN",
                "contractCode": self.contract_code,
                "customerEmail": user.email or f"{user.username}@example.com",
                "customerName": full_name[:50],
                "getAllAvailableBanks": True  # FIXED: Changed from False to True
                # DO NOT include preferredBanks when getAllAvailableBanks=true
            }
            
            # Add optional KYC data if provided
            if bvn:
                payload["bvn"] = bvn
                logger.info("Adding BVN for enhanced limits")
            
            if nin:
                payload["nin"] = nin
                logger.info("Adding NIN for enhanced limits")
            
            logger.info(f"Creating reserved account for: {user.username}")
            logger.info(f"Payload: {payload}")
            
            response = self._make_request(
                'POST',
                '/api/v2/bank-transfer/reserved-accounts',
                data=payload
            )
            
            logger.info(f"Raw response: {response}")
            
            # Check for service unavailable error
            if response and response.get('error') == 'service_unavailable':
                logger.error(f"Monnify service unavailable: {response.get('message')}")
                return {'error': 'service_unavailable', 'message': response.get('message')}
            
            if not response or not response.get('requestSuccessful'):
                error_msg = response.get('responseMessage', 'Unknown error') if response else 'No response'
                logger.error(f"Monnify API error: {error_msg}")
                logger.error(f"Full response: {response}")
                return None
            
            response_body = response.get('responseBody', {})
            accounts = response_body.get('accounts', [])
            
            if not accounts:
                logger.error(f"No bank accounts in response. Response body: {response_body}")
                return None
            
            logger.info(f"Reserved account created: {account_reference} - {len(accounts)} banks received")
            
            # Filter to prioritize Moniepoint accounts (optional - you can return all)
            moniepoint_accounts = [acc for acc in accounts if acc.get('bankCode') == '50515']
            
            # If Moniepoint exists, show it first, otherwise show all
            if moniepoint_accounts:
                logger.info(f"Found {len(moniepoint_accounts)} Moniepoint account(s)")
                primary_accounts = moniepoint_accounts
            else:
                logger.info("No Moniepoint accounts, using all available banks")
                primary_accounts = accounts
            
            return {
                'account_reference': response_body.get('accountReference'),
                'account_name': response_body.get('accountName'),
                'accounts': primary_accounts,  # Primary accounts to display
                'all_accounts': accounts,  # All accounts for reference
                'bvn': bvn,
                'nin': nin,
                'monnify_response': response_body
            }
            
        except Exception as e:
            logger.error(f"Exception in create_reserved_account: {str(e)}", exc_info=True)
            return None
    
    def init_one_time_payment(self, user_account, amount=None):
        """
        Initialize one-time payment with separate account details fetch
        Uses Moniepoint (50515) as preferred bank
        """
        try:
            import time
            import uuid
            
            logger.info("=" * 50)
            logger.info("Starting init_one_time_payment")
            
            timestamp = int(time.time())
            short_id = str(uuid.uuid4()).replace('-', '')[:8].upper()
            payment_reference = f"PAY{timestamp}{short_id}"
            
            user = user_account.user
            full_name = user.get_full_name() or user.username
            
            if not amount:
                amount = 1000.00
            
            # STEP 1: Initialize transaction
            init_payload = {
                "amount": float(amount),
                "customerName": full_name[:100],
                "customerEmail": user.email or f"{user.username}@example.com",
                "paymentReference": payment_reference,
                "paymentDescription": "Quick deposit to wallet",
                "currencyCode": "NGN",
                "contractCode": self.contract_code,
                "redirectUrl": "https://example.com/callback",
                "paymentMethods": ["ACCOUNT_TRANSFER"]
            }
            
            logger.info(f"Init payload: {init_payload}")
            
            init_response = self._make_request(
                'POST',
                '/api/v1/merchant/transactions/init-transaction',
                data=init_payload
            )
            
            if not init_response or not init_response.get('requestSuccessful'):
                logger.error("Init transaction failed")
                return None
            
            response_body = init_response.get('responseBody')
            if not response_body:
                logger.error("No responseBody in init response")
                return None
            
            transaction_reference = response_body.get('transactionReference')
            if not transaction_reference:
                logger.error("No transactionReference in response")
                return None
            
            logger.info(f"Transaction initialized: {transaction_reference}")
            
            # STEP 2: Get bank account details for Moniepoint
            bank_code = "50515"  # Moniepoint MFB
            
            account_details_payload = {
                "transactionReference": transaction_reference,
                "bankCode": bank_code
            }
            
            logger.info(f"Fetching account details for Moniepoint (bank code: {bank_code})...")
            
            account_response = self._make_request(
                'POST',
                '/api/v1/merchant/bank-transfer/init-payment',
                data=account_details_payload
            )
            
            # Extract account details
            account_name = None
            accounts = []
            
            if account_response and account_response.get('requestSuccessful'):
                account_body = account_response.get('responseBody', {})
                account_name = account_body.get('accountName')
                
                # Create account entry
                accounts.append({
                    'bankName': account_body.get('bankName'),
                    'accountNumber': account_body.get('accountNumber'),
                    'bankCode': account_body.get('bankCode')
                })
                
                logger.info(f"Account details fetched: {account_body.get('bankName')} - {account_body.get('accountNumber')}")
            else:
                logger.warning("Failed to fetch account details, will use checkout URL only")
            
            result = {
                'transaction_reference': transaction_reference,
                'payment_reference': payment_reference,
                'checkout_url': response_body.get('checkoutUrl'),
                'account_name': account_name,
                'accounts': accounts,
                'amount': amount,
                'monnify_response': response_body
            }
            
            logger.info(f"Success! Returning result with {len(accounts)} account(s)")
            logger.info("=" * 50)
            
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return None
    
    def get_transaction_status(self, transaction_reference):
        """Query transaction status from Monnify"""
        try:
            logger.info(f"Querying transaction status: {transaction_reference}")
            
            response = self._make_request(
                'GET',
                f'/api/v2/transactions/{transaction_reference}'
            )
            
            if response and response.get('requestSuccessful'):
                return response.get('responseBody')
            
            return None
            
        except Exception as e:
            logger.error(f"Error querying transaction: {str(e)}")
            return None


# Singleton instance
monnify_service = MonnifyService()