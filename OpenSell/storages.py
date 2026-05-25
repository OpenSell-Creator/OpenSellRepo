# OpenSell/storages.py
#
# Two cache policies for S3 media files:
#
#   IMMUTABLE (1 year)  — product_images/, service_images/, buyer_requests/
#       Every file in these paths has a UUID in its name so the same URL is
#       never reused for different content.  Browsers and CDNs can cache
#       forever; when a product is deleted the file is removed from S3 so a
#       cached URL simply 404s (harmless).  When a seller replaces an image
#       the new file gets a new UUID path, so the old cached URL is abandoned
#       naturally.
#
#   REVALIDATE (1 day)  — categories/, banners/, and anything else
#       Admins can swap out a category icon or banner at any time, keeping
#       the same S3 key.  A 1-day max-age means stale content is gone within
#       24 hours without hammering S3 on every page load.

from storages.backends.s3boto3 import S3Boto3Storage

# Paths whose files can be replaced at the same S3 key by admins.
# Add any new "replaceable" prefixes here as the project grows.
_MUTABLE_PREFIXES = (
    'categories/',
    'banners/',
    'profile_photos/',
    'avatars/',
)

_IMMUTABLE_CACHE  = 'public, max-age=31536000, immutable'
_REVALIDATE_CACHE = 'public, max-age=86400, must-revalidate'


class SmartMediaStorage(S3Boto3Storage):
    """
    Single media storage backend that applies the right Cache-Control header
    based on the upload path.

    UUID-named content (product/service/request images) → 1 year immutable.
    Admin-replaceable assets (category icons, banners) → 1 day revalidate.
    """

    location = 'media'

    def get_object_parameters(self, name):
        params = super().get_object_parameters(name)
        if any(name.startswith(p) for p in _MUTABLE_PREFIXES):
            params['CacheControl'] = _REVALIDATE_CACHE
        else:
            params['CacheControl'] = _IMMUTABLE_CACHE
        return params