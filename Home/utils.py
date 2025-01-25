def user_listing_path(instance, filename):
    if hasattr(instance, 'seller'):
        return f'product_images/{instance.seller.user.username}/{filename}'
    elif hasattr(instance, 'product'):
        # This is a Product_Image instance
        return f'product_images/{instance.product.seller.user.username}/{filename}'
    else:
        # Fallback
        return f'product_images/{filename}'
   