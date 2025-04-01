def user_listing_path(instance, filename):
    product = instance.product
    # Check if product has an ID (it may not during first save)
    if not product.id:
        # This is a temporary path that will be corrected later
        return f'product_images/temp/{filename}'
    return f'product_images/{product.seller.user.username}/{product.id}/{filename}'


def category_image_path(instance, filename):
    return f'categories/{instance.name}/{filename}'