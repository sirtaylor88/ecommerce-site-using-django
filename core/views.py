from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required # for function based view
from django.contrib.auth.mixins import LoginRequiredMixin # for class based view
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View
from django.utils import timezone

from .forms import CheckoutForm, CouponForm

from .models import Item, OrderItem, Order, BillingAddress, Payment, Coupon

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Create your views here.
class HomeView(ListView):
    model         = Item
    paginate_by   = 10
    ordering      = ['-id'] # minus = descending
    template_name = "home.html"

class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                "object": order
            }
            return render(self.request, "order_summary.html", context)
        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an active order.")
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
                "order": Order.objects.get(user=self.request.user, ordered=False),
                "DISPLAY_COUPON_FORM": True
            }
            return render(self.request, "checkout.html", context)
        except ObjectDoesNotExist:
            messages.info(self.request, "You don't have an active order.")
            return redirect("core:checkout")


    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                street_address = form.cleaned_data.get("street_address")
                apartment_address = form.cleaned_data.get("apartment_address")
                country = form.cleaned_data.get("country")
                postal_code = form.cleaned_data.get("postal_code")
                # TODO: add functionality for these fields
                # same_shipping_address = form.cleaned_data.get("same_shipping_address")
                # save_info = form.cleaned_data.get("save_info")
                payment_option = form.cleaned_data.get("payment_option")
                billing_address = BillingAddress(
                    user              = self.request.user,
                    street_address    = street_address,
                    apartment_address = apartment_address,
                    country           = country,
                    postal_code       = postal_code
                )
                billing_address.save()
                order.billing_address = billing_address
                order.save()

                if payment_option == "S" :
                    return redirect("core:payment", payment_option="stripe")
                elif payment_option == "P":
                    return redirect("core:payment", payment_option="paypal")
                else:
                    messages.warning(self.request, "Invalid payment option selected.")
                    return redirect("core:checkout")
        except ObjectDoesNotExist:
            messages.error(self.request, "You do not have an active order.")
            return redirect("core:order-summary")

class PaymentView(View):
    def get(self, *args, **kwargs):
        order  = Order.objects.get(user=self.request.user, ordered=False)
        context = {
            "order": order,
            "DISPLAY_COUPON_FORM": False,
        }
        return render(self.request, "payment.html", context)

    def post(self, *args, **kwargs):
        order  = Order.objects.get(user=self.request.user, ordered=False)
        token  = self.request.POST.get("stripeToken")

        try:
            charge = stripe.Charge.create(
                amount        = int(order.get_total() * 100), # value in cents
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
            order_items.update(ordered=True) # update_all

            for item in order_items:
                item.save()

            order.ordered = True
            order.payment = payment
            order.save()

            messages.success(self.request, "Your order was successful.")
            return redirect("/")

        except stripe.error.CardError as e:
            messages.error(self.request, f"{e.error.message}")
            return redirect("/")
        except stripe.error.RateLimitError as e:
            messages.error(self.request, "Rate limit error")
            return redirect("/")
        except stripe.error.InvalidRequestError as e:
            messages.error(self.request, f"{e.error.message}")
            messages.error(self.request, "Invalid parameters")
            return redirect("/")
        except stripe.error.AuthenticationError as e:
            messages.error(self.request, "Not authenticated")
            return redirect("/")
        except stripe.error.APIConnectionError as e:
            messages.error(self.request, "Network error")
            return redirect("/")
        except stripe.error.StripeError as e:
            messages.error(self.request, "Something went wrong. You are not charged. Please try again.")
            return redirect("/")
        except Exception as e:
            # send an email to ourselves
            messages.error(self.request, "A serious error occured. We have been notified")
            return redirect("/")

def products(request):
    template = "products.html"
    context = {
        "items": Item.objects.all()
    }
    return render(request, template, context)

@login_required
def add_to_cart(request, slug):
    item       = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    order_qs   = Order.objects.filter(
        user=request.user,
        ordered=False
    )

    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
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
    item       = get_object_or_404(Item, slug=slug)
    order_qs   = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            messages.info(request, "This item was removed from your cart.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("core:product", slug=slug)

    else:
        messages.info(request, "You don't have an active order.")
        return redirect("core:product", slug=slug)

@login_required
def remove_single_item_from_cart(request, slug):
    item       = get_object_or_404(Item, slug=slug)
    order_qs   = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
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
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "This coupon does not exist")
        return redirect("core:checkout")

def add_coupon(request):
    if request.method == "POST":
        form = CouponForm(request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get("code")
                order = Order.objects.get(user=request.user, ordered=False)
                order.coupon = get_coupon(request, code)
                order.save()
                messages.success(request, "Successfully added coupon")
                return redirect("core:checkout")
            except ObjectDoesNotExist:
                messages.info(request, "You don't have an active order.")
                return redirect("core:checkout")
    # TODO: raise error
    return None
