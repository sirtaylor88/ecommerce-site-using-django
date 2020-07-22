from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required # for function based view
from django.contrib.auth.mixins import LoginRequiredMixin # for class based view
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View
from django.utils import timezone

from .forms import CheckoutForm, CouponForm, RefundForm, PaymentForm

from .models import Item, OrderItem, Order, Address, Payment, Coupon, Refund, UserProfile

import random
import string
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

def create_ref_code():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=20))

def is_valid_form(values):
    valid = True
    for field in values:
        if field == "":
            valid = False
    return valid

# Create your views here.
class HomeView(ListView):
    model         = Item
    paginate_by   = 10
    ordering      = ['-id'] # minus = descending
    template_name = "home.html"

class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            context = {
                "object": Order.objects.get(
                    user    = self.request.user,
                    ordered = False
                )
            }
            return render(self.request, "order_summary.html", context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order.")
            return redirect("/")

class ItemDetailView(DetailView):
    model         = Item
    template_name = "product.html"

class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            context = {
                "form": CheckoutForm(),
                "coupon_form": CouponForm(),
                "order": Order.objects.get(
                    user    = self.request.user,
                    ordered = False
                ),
                "DISPLAY_COUPON_FORM": True
            }

            shipping_address_qs = Address.objects.filter(
                user         = self.request.user,
                address_type = "S",
                default      = True
            )
            if shipping_address_qs.exists():
                context.update(
                    { "default_shipping_address": shipping_address_qs[0] }
                )

            billing_address_qs = Address.objects.filter(
                user         = self.request.user,
                address_type = "B",
                default      = True
            )
            if billing_address_qs.exists():
                context.update(
                    { "default_billing_address": billing_address_qs[0] }
                )

            return render(self.request, "checkout.html", context)
        except ObjectDoesNotExist:
            messages.info(self.request, "You don't have an active order.")
            return redirect("core:checkout")


    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(
                user    = self.request.user,
                ordered = False
            )
            if form.is_valid():
                print(form.cleaned_data)
                use_default_shipping = form.cleaned_data.get("use_default_shipping")
                if use_default_shipping:
                    print("Use the default shipping address")
                    address_qs = Address.objects.filter(
                        user         = self.request.user,
                        address_type = "S",
                        default      = True
                    )
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.info(self.request, "No default shipping address available.")
                        return redirect("core:checkout")
                else:
                    print("User is entering a new shipping address.")
                    shipping_address_1    = form.cleaned_data.get("shipping_address_1")
                    shipping_address_2    = form.cleaned_data.get("shipping_address_2")
                    shipping_country      = form.cleaned_data.get("shipping_country")
                    shipping_postal_code  = form.cleaned_data.get("shipping_postal_code")

                    if is_valid_form([shipping_address_1, shipping_country, shipping_postal_code]):
                        shipping_address  = Address(
                            user              = self.request.user,
                            street_address    = shipping_address_1,
                            apartment_address = shipping_address_2,
                            country           = shipping_country,
                            postal_code       = shipping_postal_code,
                            address_type      = "S"
                        )
                        shipping_address.save()

                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping  = form.cleaned_data.get("set_default_shipping")
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()
                    else:
                        messages.info(self.request, "Please fill in the required shipping address field.")

                use_default_billing  = form.cleaned_data.get("use_default_billing")
                same_billing_address = form.cleaned_data.get("same_billing_address")

                if same_billing_address:
                    billing_address              = shipping_address
                    billing_address.pk           = None # autogenerate new primary key for new object
                    billing_address.save()              # save duplicated object
                    billing_address.address_type = "B"
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()

                elif use_default_billing:
                    print("Use the default billing address")
                    address_qs = Address.objects.filter(
                        user         = self.request.user,
                        address_type = "B",
                        default      = True
                    )
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.info(self.request, "No default billing address available.")
                        return redirect("core:checkout")

                else:
                    print("User is entering a new billing address.")
                    billing_address_1    = form.cleaned_data.get("billing_address_1")
                    billing_address_2    = form.cleaned_data.get("billing_address_2")
                    billing_country      = form.cleaned_data.get("billing_country")
                    billing_postal_code  = form.cleaned_data.get("billing_postal_code")

                    if is_valid_form([billing_address_1, billing_country, billing_postal_code]):
                        billing_address  = Address(
                            user              = self.request.user,
                            street_address    = billing_address_1,
                            apartment_address = billing_address_2,
                            country           = billing_country,
                            postal_code       = billing_postal_code,
                            address_type      = "B"
                        )
                        billing_address.save()

                        order.billing_address = billing_address
                        order.save()

                        set_default_billing  = form.cleaned_data.get("set_default_billing")
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()
                    else:
                        messages.info(self.request, "Please fill in the required billing address field.")

                payment_option        = form.cleaned_data.get("payment_option")

                if payment_option == "S" :
                    return redirect("core:payment", payment_option="stripe")
                elif payment_option == "P":
                    return redirect("core:payment", payment_option="paypal")
                else:
                    messages.warning(self.request, "Invalid payment option selected.")
                    return redirect("core:checkout")
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order.")
            return redirect("core:order-summary")

class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(
            user    = self.request.user,
            ordered = False
        )

        if order.billing_address:
            context = {
                "order": order,
                "DISPLAY_COUPON_FORM": False
            }
            user_profile = self.request.user.userprofile
            if user_profile.one_click_purchasing:
                # fetch the user card list
                cards = stripe.Customer.list_sources(
                    user_profile.stripe_customer_id,
                    limit  = 3,
                    object = "card"
                )
                card_list = cards["data"]
                if len(card_list) > 0:
                    # update the context with default card
                    context.update({"card": card_list[0]})

            return render(self.request, "payment.html", context)
        else:
            messages.warning(self.request, "You have not add a billing address")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        order        = Order.objects.get(
            user    = self.request.user,
            ordered = False
        )
        form         = PaymentForm(self.request.POST)
        user_profile = UserProfile.objects.get(user = self.request.user)

        if form.is_valid():
            print(form.cleaned_data)
            token       = self.request.POST.get("stripeToken")
            save        = form.cleaned_data.get("save")
            use_default = form.cleaned_data.get("use_default")

            if save:
                # allow to fetch cards
                if not user_profile.stripe_customer_id:
                    customer = stripe.Customer.create(
                        email  = self.request.user.email,
                        source = token
                    )
                    user_profile.stripe_customer_id   = customer["id"]
                    user_profile.one_click_purchasing = True
                    user_profile.save()
                else:
                    stripe.Customer.create_source(
                        user_profile.stripe_customer_id,
                        source = token
                    )
            amount = int(order.get_total() * 100) # cents

        try:
            if use_default:
                charge = stripe.Charge.create(
                    amount        = amount, # cents
                    currency      = "eur",
                    customer      = user_profile.stripe_customer_id
                )
            else:
                charge = stripe.Charge.create(
                    amount        = amount, # cents
                    currency      = "eur",
                    source        = token
                )
            # create the payment
            payment = Payment(
                stripe_charge_id = charge["id"],
                user             = self.request.user,
                amount           = order.get_total()
            )
            payment.save()

            # assign the payment to the order
            order_items = order.items.all()
            order_items.update(ordered = True) # update_all

            for item in order_items:
                item.save()

            order.ordered = True
            order.ref_code = create_ref_code()
            order.payment = payment
            order.save()

            messages.success(self.request, "Your order was successful.")
            return redirect("/")

        except stripe.error.CardError as e:
            messages.warning(self.request, f"{e.error.message}")
            return redirect("/")
        except stripe.error.RateLimitError as e:
            messages.warning(self.request, "Rate limit error")
            return redirect("/")
        except stripe.error.InvalidRequestError as e:
            messages.warning(self.request, f"{e.error.message}")
            messages.warning(self.request, "Invalid parameters")
            return redirect("/")
        except stripe.error.AuthenticationError as e:
            messages.warning(self.request, "Not authenticated")
            return redirect("/")
        except stripe.error.APIConnectionError as e:
            messages.warning(self.request, "Network error")
            return redirect("/")
        except stripe.error.StripeError as e:
            messages.warning(self.request, "Something went wrong. You are not charged. Please try again.")
            return redirect("/")
        except Exception as e:
            messages.warning(self.request, f"{e.error.message}")
            # send an email to ourselves
            messages.warning(self.request, "A serious error occured. We have been notified")
            return redirect("/")

def products(request):
    template = "products.html"
    context = {
        "items": Item.objects.all()
    }
    return render(request, template, context)

@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug = slug)
    order_item, created = OrderItem.objects.get_or_create(
        item    = item,
        user    = request.user,
        ordered = False
    )
    order_qs = Order.objects.filter(
        user    = request.user,
        ordered = False
    )

    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug = item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item quantity was updated.")
            return redirect("core:order-summary")
        else:
            order.items.add(order_item)
            messages.info(request, "This item was added to your cart.")
            return redirect("core:order-summary")
    else:
        order = Order.objects.create(
            user=request.user,
            ordered_date= timezone.now()
        )
        order.items.add(order_item)
        messages.info(request, "This item was added to your cart.")
        return redirect("core:order-summary")

@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug = slug)
    order_qs = Order.objects.filter(
        user    = request.user,
        ordered = False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug = item.slug).exists():
            order_item = OrderItem.objects.filter(
                item    = item,
                user    = request.user,
                ordered = False
            )[0]
            order.items.remove(order_item)
            messages.info(request, "This item was removed from your cart.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("core:product", slug = slug)

    else:
        messages.info(request, "You don't have an active order.")
        return redirect("core:product", slug = slug)

@login_required
def remove_single_item_from_cart(request, slug):
    item       = get_object_or_404(Item, slug = slug)
    order_qs   = Order.objects.filter(
        user    = request.user,
        ordered = False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug = item.slug).exists():
            order_item = OrderItem.objects.filter(
                item    = item,
                user    = request.user,
                ordered = False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
                messages.info(request, "This item quantity was updated.")
            else:
                order.items.remove(order_item)
                messages.info(request, "This item was removed from your cart.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("core:order-summary")

    else:
        messages.info(request, "You don't have an active order.")
        return redirect("core:order-summary")

def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code = code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "This coupon does not exist")
        return redirect("core:checkout")

class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get("code")
                order = Order.objects.get(
                    user    = self.request.user,
                    ordered = False
                )
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully added coupon")
                return redirect("core:checkout")
            except ObjectDoesNotExist:
                messages.info(self.request, "You don't have an active order.")
                return redirect("core:checkout")

class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            "form": form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code  = form.cleaned_data.get("ref_code")
            message   = form.cleaned_data.get("message")
            email     = form.cleaned_data.get("email")
            try:
                order = Order.objects.get(ref_code = ref_code)
                order.refund_requested = True
                order.save()
                refund = Refund(
                    order  = order,
                    reason = message,
                    email  = email
                )
                refund.save()
                messages.info(self.request, "Your request was received.")
                return redirect("core:request-refund")
            except ObjectDoesNotExist:
                messages.info(self.request, "This order does not exist")
                return redirect("core:request-refund")
