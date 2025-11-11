import logging

logger = logging.getLogger(__name__)


class ReferralCodeMiddleware:
    """
    Middleware to capture and preserve referral codes across OAuth flows
    UPDATED: Sets default 'opensell' referral code if none provided
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Capture referral code from URL
        referral_code = request.GET.get('ref', '').strip()
        
        # UPDATED: Use default referral code if none provided
        if not referral_code and 'referral_code' not in request.session:
            referral_code = 'opensell'
        
        if referral_code:
            # Validate it before storing
            try:
                from Dashboard.models import AffiliateProfile
                affiliate = AffiliateProfile.objects.get(
                    referral_code__iexact=referral_code,
                    status='active'
                )
                # Store in session
                request.session['referral_code'] = referral_code
                request.session.modified = True
                logger.debug(f"Referral code {referral_code} stored in session")
            except AffiliateProfile.DoesNotExist:
                logger.warning(f"Invalid referral code attempted: {referral_code}")
                # If invalid and it's not the default, try the default
                if referral_code != 'opensell':
                    try:
                        default_affiliate = AffiliateProfile.objects.get(
                            referral_code__iexact='opensell',
                            status='active'
                        )
                        request.session['referral_code'] = 'opensell'
                        request.session.modified = True
                        logger.debug("Set default referral code 'opensell'")
                    except AffiliateProfile.DoesNotExist:
                        logger.error("Default referral code 'opensell' not found!")
        
        response = self.get_response(request)
        return response