import json
import logging
import hashlib
from decimal import Decimal
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User

from .models import (
    UserAccount, VirtualAccount, MonnifyTransaction,
    PaymentNotification
)

logger = logging.getLogger(__name__)


def calculate_transaction_hash(payload, client_secret):
    """Calculate transaction hash for webhook validation"""
    try:
        payment_ref = str(payload.get('paymentReference', ''))
        amount_paid = str(payload.get('amountPaid', ''))
        paid_on = str(payload.get('paidOn', ''))
        transaction_ref = str(payload.get('transactionReference', ''))
        
        hash_string = f"{payment_ref}{amount_paid}{paid_on}{transaction_ref}{client_secret}"
        computed_hash = hashlib.sha512(hash_string.encode('utf-8')).hexdigest()
        
        logger.debug(f"Hash calculated for txn: {transaction_ref[:20]}...")
        return computed_hash
        
    except Exception as e:
        logger.error(f"Error calculating hash: {str(e)}", exc_info=True)
        return None


@csrf_exempt
@require_http_methods(["POST", "GET"])
def monnify_webhook(request):
    """
    Enhanced webhook handler with detailed error logging
    """
    try:
        # Log request details
        logger.info("="*80)
        logger.info("WEBHOOK REQUEST RECEIVED")
        logger.info("="*80)
        logger.info(f"Method: {request.method}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Path: {request.path}")
        
        # Get client IP
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', 
                                     request.META.get('REMOTE_ADDR', 'Unknown'))
        logger.info(f"Client IP: {client_ip}")
        
        # Handle GET requests (for testing)
        if request.method == "GET":
            logger.info("GET request received - webhook is reachable")
            return JsonResponse({
                'status': 'success',
                'message': 'Monnify webhook endpoint is active',
                'method': 'GET'
            })
        
        # Get raw body
        try:
            raw_body = request.body.decode('utf-8')
            logger.info(f"Raw Body Length: {len(raw_body)} bytes")
            logger.debug(f"Raw Body: {raw_body[:1000]}")
        except Exception as e:
            logger.error(f"Error decoding body: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request body encoding'
            }, status=400)
        
        # Check if body is empty
        if not raw_body or raw_body.strip() == '':
            logger.error("Empty request body received")
            return JsonResponse({
                'status': 'error',
                'message': 'Empty request body'
            }, status=400)
        
        # Parse JSON
        try:
            data = json.loads(raw_body)
            logger.info(f"Parsed JSON successfully")
            logger.info(f"JSON Keys: {list(data.keys())}")
            logger.debug(f"Full Payload: {json.dumps(data, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            logger.error(f"Failed to parse: {raw_body}")
            return JsonResponse({
                'status': 'error',
                'message': f'Invalid JSON: {str(e)}'
            }, status=400)
        
        # Determine webhook format
        if 'eventType' in data and 'eventData' in data:
            logger.info(f"Event-based webhook format detected: {data.get('eventType')}")
            return process_event_based_webhook(data)
        elif 'transactionReference' in data or 'paymentReference' in data:
            logger.info("Legacy webhook format detected")
            return process_legacy_webhook(data)
        else:
            logger.error("Unknown webhook format - no recognized fields")
            logger.error(f"Available fields: {list(data.keys())}")
            return JsonResponse({
                'status': 'error',
                'message': 'Unknown webhook format',
                'received_fields': list(data.keys())
            }, status=400)
            
    except Exception as e:
        logger.error("="*80)
        logger.error("CRITICAL WEBHOOK ERROR")
        logger.error("="*80)
        logger.error(f"Error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)


def process_event_based_webhook(data):
    """Process EVENT-BASED webhook format - FIXED for one-time payments"""
    try:
        event_type = data.get('eventType')
        event_data = data.get('eventData', {})
        
        logger.info(f"Processing event webhook - Type: {event_type}")
        
        if event_type != 'SUCCESSFUL_TRANSACTION':
            logger.info(f"Non-payment event received: {event_type}")
            return JsonResponse({
                'status': 'success',
                'message': f'Event {event_type} acknowledged'
            })
        
        transaction_reference = event_data.get('transactionReference')
        payment_reference = event_data.get('paymentReference')
        
        logger.info(f"Transaction Ref: {transaction_reference}")
        logger.info(f"Payment Ref: {payment_reference}")
        
        # Check for duplicate
        if MonnifyTransaction.objects.filter(transaction_reference=transaction_reference).exists():
            logger.info(f"Duplicate transaction: {transaction_reference}")
            return JsonResponse({
                'status': 'success',
                'message': 'Transaction already processed'
            })
        
        # Extract product reference
        product = event_data.get('product', {})
        product_reference = product.get('reference')
        product_type = product.get('type')
        
        logger.info(f"Product reference: {product_reference}, Type: {product_type}")
        
        # Initialize variables
        virtual_account = None
        user_account = None
        
        # FIXED: Handle different payment types
        if product_reference and product_reference.startswith('VA-'):
            # This is a PERMANENT virtual account payment
            logger.info(f"Looking for virtual account: {product_reference}")
            virtual_account = VirtualAccount.objects.filter(
                account_reference=product_reference,
                status='active'
            ).select_related('user_account').first()
            
            if not virtual_account:
                logger.error(f"Virtual account not found: {product_reference}")
                PaymentNotification.objects.create(
                    notification_type='FAILED_TRANSACTION',
                    transaction_reference=transaction_reference,
                    processed=False,
                    processing_error=f'Virtual account not found: {product_reference}',
                    raw_payload=data
                )
                return JsonResponse({
                    'status': 'error',
                    'message': 'Virtual account not found',
                    'product_reference': product_reference
                }, status=404)
            
            user_account = virtual_account.user_account
            logger.info(f"Found virtual account for user: {user_account.user.username}")
            
        elif product_reference and (product_reference.startswith('PAY') or product_type == 'API_NOTIFICATION'):
            # This is a ONE-TIME PAYMENT (init-transaction)
            logger.info(f"One-time payment detected: {product_reference}")
            
            # Try to find user by email from customer data
            customer = event_data.get('customer', {})
            customer_email = customer.get('email', '').strip().lower()
            
            logger.info(f"Searching for user by email: {customer_email}")
            
            if customer_email:
                try:
                    user = User.objects.filter(email__iexact=customer_email).first()
                    
                    if user:
                        user_account = UserAccount.objects.filter(user=user).first()
                        if user_account:
                            logger.info(f"Found user account for: {user.username}")
                        else:
                            logger.error(f"User found but no UserAccount: {user.username}")
                    else:
                        logger.error(f"No user found with email: {customer_email}")
                except Exception as e:
                    logger.error(f"Error finding user: {str(e)}", exc_info=True)
            else:
                logger.error("No customer email in webhook data")
            
            if not user_account:
                logger.error(f"Cannot identify user for one-time payment: {payment_reference}")
                PaymentNotification.objects.create(
                    notification_type='FAILED_TRANSACTION',
                    transaction_reference=transaction_reference,
                    processed=False,
                    processing_error=f'User not found for email: {customer_email}',
                    raw_payload=data
                )
                return JsonResponse({
                    'status': 'error',
                    'message': 'User account not found',
                    'email': customer_email
                }, status=404)
        else:
            logger.error(f"Unknown payment type. Reference: {product_reference}, Type: {product_type}")
            PaymentNotification.objects.create(
                notification_type='FAILED_TRANSACTION',
                transaction_reference=transaction_reference,
                processed=False,
                processing_error='Unknown payment type',
                raw_payload=data
            )
            return JsonResponse({
                'status': 'error',
                'message': 'Unknown payment type'
            }, status=400)
        
        # Parse payment date
        paid_on_str = event_data.get('paidOn', timezone.now().isoformat())
        try:
            # Handle different date formats
            if '.' in paid_on_str:
                # Format: "2025-10-28 16:23:50.0"
                paid_on = datetime.strptime(paid_on_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
            else:
                paid_on = datetime.fromisoformat(paid_on_str.replace('Z', '+00:00'))
            
            if timezone.is_naive(paid_on):
                paid_on = timezone.make_aware(paid_on)
        except Exception as e:
            logger.warning(f"Date parse error: {e}, using current time")
            paid_on = timezone.now()
        
        # Extract payment details
        payment_sources = event_data.get('paymentSourceInformation', [])
        first_source = payment_sources[0] if payment_sources else {}
        customer = event_data.get('customer', {})
        
        # Create transaction record
        logger.info("Creating MonnifyTransaction record...")
        monnify_txn = MonnifyTransaction.objects.create(
            user_account=user_account,
            virtual_account=virtual_account,  # Can be None for one-time payments
            transaction_reference=transaction_reference,
            payment_reference=payment_reference,
            amount_paid=Decimal(str(event_data.get('amountPaid', 0))),
            total_payable=Decimal(str(event_data.get('totalPayable', 0))),
            settlement_amount=Decimal(str(event_data.get('settlementAmount', 0))),
            paid_on=paid_on,
            payment_status='PAID',
            payment_description=event_data.get('paymentDescription', ''),
            payment_method=event_data.get('paymentMethod', 'ACCOUNT_TRANSFER'),
            currency=event_data.get('currencyCode', 'NGN'),
            customer_name=customer.get('name', ''),
            customer_email=customer.get('email', ''),
            destination_account_number=first_source.get('accountNumber', ''),
            destination_account_name=first_source.get('accountName', ''),
            destination_bank_code=first_source.get('bankCode', ''),
            webhook_payload=data,
            processed=False
        )
        
        logger.info(f"Transaction record created: ID={monnify_txn.id}")
        
        # Process payment (credit user account)
        logger.info("Processing payment...")
        success = monnify_txn.process_payment()
        
        # Create notification
        PaymentNotification.objects.create(
            notification_type='SUCCESSFUL_TRANSACTION',
            transaction_reference=transaction_reference,
            monnify_transaction=monnify_txn,
            processed=success,
            processed_at=timezone.now() if success else None,
            processing_error='' if success else 'Failed to credit account',
            raw_payload=data
        )
        
        if success:
            logger.info("="*80)
            logger.info("✓ PAYMENT PROCESSED SUCCESSFULLY")
            logger.info(f"Transaction: {transaction_reference}")
            logger.info(f"Amount: ₦{event_data.get('amountPaid')}")
            logger.info(f"User: {user_account.user.username}")
            logger.info(f"Payment Type: {'Virtual Account' if virtual_account else 'One-Time Payment'}")
            logger.info(f"New Balance: ₦{user_account.balance}")
            logger.info("="*80)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Payment processed successfully'
            })
        else:
            logger.error(f"✗ Failed to process payment: {transaction_reference}")
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to process payment'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error processing event webhook: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Processing error'
        }, status=500)


def process_legacy_webhook(data):
    """Process LEGACY webhook format"""
    try:
        logger.info("Processing legacy webhook...")
        
        # Extract critical fields
        transaction_reference = data.get('transactionReference')
        payment_reference = data.get('paymentReference')
        amount_paid = data.get('amountPaid')
        payment_status = data.get('paymentStatus')
        transaction_hash = data.get('transactionHash')
        
        # Log extracted fields
        logger.info(f"Transaction Ref: {transaction_reference}")
        logger.info(f"Payment Ref: {payment_reference}")
        logger.info(f"Amount: {amount_paid}")
        logger.info(f"Status: {payment_status}")
        
        # Validate required fields
        if not all([transaction_reference, payment_reference, amount_paid, payment_status]):
            missing_fields = []
            if not transaction_reference: missing_fields.append('transactionReference')
            if not payment_reference: missing_fields.append('paymentReference')
            if not amount_paid: missing_fields.append('amountPaid')
            if not payment_status: missing_fields.append('paymentStatus')
            
            logger.error(f"Missing required fields: {missing_fields}")
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields',
                'missing_fields': missing_fields
            }, status=400)
        
        # Only process PAID transactions
        if payment_status != 'PAID':
            logger.warning(f"Non-PAID transaction: {payment_status}")
            PaymentNotification.objects.create(
                notification_type=f"{payment_status}_TRANSACTION",
                transaction_reference=transaction_reference,
                processed=True,
                raw_payload=data
            )
            return JsonResponse({
                'status': 'success',
                'message': f'Transaction status {payment_status} noted'
            })
        
        # Check for duplicate
        if MonnifyTransaction.objects.filter(transaction_reference=transaction_reference).exists():
            logger.info(f"Duplicate transaction ignored: {transaction_reference}")
            return JsonResponse({
                'status': 'success',
                'message': 'Transaction already processed'
            })
        
        # Find virtual account
        product_ref = data.get('product', {}).get('reference')
        if not product_ref:
            logger.error("No product reference in webhook data")
            PaymentNotification.objects.create(
                notification_type='FAILED_TRANSACTION',
                transaction_reference=transaction_reference,
                processed=False,
                processing_error='No product reference found',
                raw_payload=data
            )
            return JsonResponse({
                'status': 'error',
                'message': 'No product reference found'
            }, status=400)
        
        logger.info(f"Looking for virtual account: {product_ref}")
        
        virtual_account = VirtualAccount.objects.filter(
            account_reference=product_ref,
            status='active'
        ).select_related('user_account').first()
        
        if not virtual_account:
            logger.error(f"Virtual account not found: {product_ref}")
            PaymentNotification.objects.create(
                notification_type='FAILED_TRANSACTION',
                transaction_reference=transaction_reference,
                processed=False,
                processing_error=f'Virtual account not found: {product_ref}',
                raw_payload=data
            )
            return JsonResponse({
                'status': 'error',
                'message': 'Virtual account not found',
                'product_reference': product_ref
            }, status=404)
        
        logger.info(f"Virtual account found for user: {virtual_account.user_account.user.username}")
        
        # Parse payment date
        paid_on_str = data.get('paidOn')
        try:
            paid_on = datetime.strptime(paid_on_str, "%d/%m/%Y %I:%M:%S %p")
            paid_on = timezone.make_aware(paid_on)
        except Exception as date_error:
            logger.warning(f"Date parse error: {date_error}, using current time")
            paid_on = timezone.now()
        
        # Extract details
        account_details = data.get('accountDetails', {})
        customer = data.get('customer', {})
        
        # Create transaction
        logger.info("Creating MonnifyTransaction record...")
        monnify_txn = MonnifyTransaction.objects.create(
            user_account=virtual_account.user_account,
            virtual_account=virtual_account,
            transaction_reference=transaction_reference,
            payment_reference=payment_reference,
            amount_paid=Decimal(str(amount_paid)),
            total_payable=Decimal(str(data.get('totalPayable', amount_paid))),
            settlement_amount=Decimal(str(data.get('settlementAmount', amount_paid))),
            paid_on=paid_on,
            payment_status='PAID',
            payment_description=data.get('paymentDescription', ''),
            payment_method=data.get('paymentMethod', 'ACCOUNT_TRANSFER'),
            currency=data.get('currencyCode', 'NGN'),
            customer_name=customer.get('name', ''),
            customer_email=customer.get('email', ''),
            destination_account_number=account_details.get('accountNumber', ''),
            destination_account_name=account_details.get('accountName', ''),
            destination_bank_code=account_details.get('bankCode', ''),
            destination_bank_name=account_details.get('bankName', ''),
            webhook_payload=data,
            processed=False
        )
        
        logger.info(f"Transaction record created: ID={monnify_txn.id}")
        
        # Process payment
        logger.info("Processing payment...")
        success = monnify_txn.process_payment()
        
        # Create notification
        PaymentNotification.objects.create(
            notification_type='SUCCESSFUL_TRANSACTION',
            transaction_reference=transaction_reference,
            monnify_transaction=monnify_txn,
            processed=success,
            processed_at=timezone.now() if success else None,
            processing_error='' if success else 'Failed to credit account',
            raw_payload=data
        )
        
        if success:
            logger.info("="*80)
            logger.info("✓ PAYMENT PROCESSED SUCCESSFULLY")
            logger.info(f"Transaction: {transaction_reference}")
            logger.info(f"Amount: ₦{amount_paid}")
            logger.info(f"User: {virtual_account.user_account.user.username}")
            logger.info(f"New Balance: ₦{virtual_account.user_account.balance}")
            logger.info("="*80)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Payment processed successfully',
                'transaction_reference': transaction_reference
            })
        else:
            logger.error(f"✗ Failed to process payment: {transaction_reference}")
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to process payment'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error processing legacy webhook: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Processing error'
        }, status=500)