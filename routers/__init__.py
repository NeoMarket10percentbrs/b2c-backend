from .auth.auth_router import auth_router
from .addresses.addresses_router import addresses_router
from .buyer.buyer_router import buyer_router
from .cart.cart_router import cart_router
from .catalog.catalog_router import catalog_router
from .favorites.favorites_router import favorites_router
from .notifications.notifications_router import notification_router
from .orders.orders_router import order_router
from .payment_methods.payment__router import payment_router
from .b2b.b2b_events_router import b2b_events_router

routes = [
    auth_router, addresses_router,
    buyer_router, cart_router,
    catalog_router, favorites_router,
    notification_router, order_router,
    payment_router, b2b_events_router
]