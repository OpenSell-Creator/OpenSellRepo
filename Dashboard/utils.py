import logging

logger = logging.getLogger(__name__)


def check_referral_fraud(referral):
    """
    DISABLED: No fraud detection as per business requirements
    
    Your business model allows unlimited referrals from any IP.
    Commissions are based on actual spending, so fraud is not a concern.
    
    Returns:
        bool: Always False (never flags anything)
    """
    return False


def check_referral_fraud_async(referral_id):
    """
    DISABLED: No async fraud checking
    """
    pass


# Log that fraud detection is disabled
logger.info("SUCCESS AFFILIATE SYSTEM: Fraud detection DISABLED - unlimited referrals allowed")