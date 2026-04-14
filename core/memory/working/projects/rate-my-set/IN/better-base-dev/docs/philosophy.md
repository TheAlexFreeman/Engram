# Philosophy

## Backstory

Before Elyon Technologies officially came to be, I (Micah) spent years as a freelance software engineer, building and launching dozens of software products, applications, or similar over a number of years.

As I built products over time, a number of things were happening:
1. I was becoming a lot more _refined_ in my craft and discipline of building, for example, full-stack Django applications.
2. I was getting a lot faster at building these applications, both from the perspective of being able to deliver products quickly, but also from the perspective of typically knowing which paths were going to prove fruitful when running into a new challenge or problem.
3. I increasingly noticed a lot of the nuances and tricky edge cases come up when building any modern software web application and wanting it to be _really good_. Sometimes there's a one size fits all solution, but often times there's not.
4. I found that a number of open source libraries, while initially attractive as an option/solution, slowed me or the projects I was working on down as time went on.

I want to highlight **4.** for a second, and give a practical example. Years ago, I worked on a project in real-estate technology that had a React frontend and a DRF backend API. It was a standard SPA, and we needed to get it off the ground quickly. I picked [djoser](https://github.com/sunscrapers/djoser) back then because it seemed like the best option and other top candidate software libraries weren't as maintained.

This worked great initially. Fast forward a little bit though, and the project suddenly
needed email _and/or_ phone verification for what it was doing (and to do certain actions both needed to be verified). Here's a small snippet of a few parts of our `UserViewSet`. Some major things to notice:
* It seemed like the best solution in one case was to completely copy and paste sone `djoser` code because there wasn't a way to override the method along to get what we want.
* We used a grandparent `super` call to deal with some `djoser` behavior that we wanted to change.
* We had to do some careful overrides of `djoser` functionality in general, and set some `djoser` `@action`s to `None` to explicitly disable them.

```
class UserViewSet(djoser_views.UserViewSet):
    """
    Custom `UserViewSet` that overrides/patches certain djoser functionality to fit
    our use case(s).

    NOTE: `User` updates require a fully verified `User`. Hence, you can't patch the
    `User` until either the `phonenumber` or `email` is verified (having `verified` set to `True`).
    Because `User` updates require a fully verified `User`, we don't send activation
    emails or phone number verifications even if an email or phone number is changed.
    We simply set `email_verified` or `phonenumber_verified` to `False`, but don't
    change `verified`. We assume right that if the `User` is verified he/she is
    not acting maliciously. If/as the project evolves, it may be necessary to
    not send emails/SMS messages until `email_verified` is `True` or `phonenumber_verified`
    is `True`, meaning that when the email or phone number is changed re-verification
    must take place. There are already API endpoints in place to send either verification.
    """
    ...

    def perform_create(self, serializer):
        """
        NOTE (2021-03-25 ~v1.4.3 when working on V2 signup flow): I opted to
        completely override `perform_create`, copy pasting Djoser's existing code and
        adding in some of our own. The reason for that is that Djoser doesn't provide
        certain hooks (which is totally fine) for inserting our code _right after_
        the `serializer.save()`, and we want to send the text message before sending
        the email (because that's more likely to run into an issue).
        """
        # (Djoser code copied on 2021-03-25 from Djoser v2.1.0, which is the latest at
        # the time of writing).
        ...

    def perform_update(self, serializer):
        # Call `perform_update` on `djoser_views.UserViewSet`'s parent `perform_update`
        # method (grandparent method call).
        # NOTE/TODO: This is currently in place because as of Djoser v2.0.5, there is
        # some logic that doesn't make sense for our use case in `perform_update` that
        # sends the activation email on every update, which we don't want right now
        # (see https://github.com/sunscrapers/djoser/issues/546).
        super(djoser_views.UserViewSet, self).perform_update(serializer)

        @action(["post"], detail=False)

    def resend_activation(self, request, *args, **kwargs):
        # Djoser's implementation at the time of writing can return a 400
        # under certain conditions. We want a 204 regardless for security/not
        # linking account info, etc. reasons.
        super().resend_activation(request, *args, **kwargs)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # NOTE: We aren't using this functionality right now, so setting the DRF
    # `action` decorator methods to `None` to not allow them right now.
    set_username = None
    reset_username = None
    reset_username_confirm = None
    
    ...

```

Now, this was already getting messy (and more difficult to maintain/test). A few months later, we added a signup referral code feature, and had to do even more plumbing to get things to work with djoser. By then, we'd added dozens of tests to make sure that signup, login, verify email, reset password, etc., were doing what we wanted them to do. But even then, adding any new functionality here or changing it was very laborious and meticulous; we had to make sure we weren't breaking things by accidentally overriding djoser functionality we wanted to keep, but also wanted to selectively tweak or disable certain djoser features and functionality.

Anyways, I want to make one thing clear. None of this is `djoser`'s fault, or indication of a bad library, or any of that. In fact, I'm very grateful for `djoser`, the people who created and maintained it, and the fact that it's out there in the open. Our problem was that we outgrew it and needed more customizability and flexibility than `djoser` (or any library in my opinion) was providing.

So, with my initial 20/20 hindsight glasses, here's what I would've done.
* First of all, I would've implemented the necessary REST authentication and related endpoints myself. Django already has a lot of the "hard stuff" done for us, we just need to create those endpoints, put the logic in the proper place, and test it.
* From there, I would've had all the necessary things in place to customize and tweak parts of the auth/signup flow as needed, and the double verification and referral code features would've taken half the time.

Now, why would they have taken half the time? Because I'm literally only working with _one codebase_ and I can find the exact piece of the code that needs to change, and add or update the tests that make sure that piece of functionality is correct. The problem with the `djoser` approach is I had to:
1. Figure out where `djoser` was handling this specific endpoint.
2. "Go to Definition" and figure out what `djoser` was doing.
3. See which method(s) I needed to override to do what I wanted to do.
4. Test and make sure I didn't break anything.

Anyways, I could keep going on about this, but in the over the medium to long run, having all of the code be in our codebase (instead of a third-party library or service) would've sped up the development on a number of features by a significant margin, and allowed us to build and iterate quicker on a lot of future things.

**BUT HERE'S THE CRUX**

Most software products or things I've seen **want it done yesterday.** Usually there is a rightly justified timeline or deadline, and that's fine, but what I've seen too many times is that the timeline or deadline causes engineering decisions to be made early on that can cause a great deal of pain and frustration in the future (typically at the 1 to 2 year mark in my experience). Having seen a lot of projects through the first, especially, 1-3 year phase and timeline, I've seen time and again what I think should be built robustly (and not necessarily offloaded to third party or existing open source solutions) and integrated as a first-class citizen in the software application.

The problem is, if I take all of these things that I've seen, they would take months to implement for a new project (implement well and correctly, tested, etc.), and most new projects don't want to take months longer. They typically have an MVP to build, things to get out quickly, and can't afford that.

**SO WHAT'S THE SOLUTION?**

The solution is, I went ahead and built these things and packaged them into a starter codebase which I call "Better Base", or BB (or bb) for short. BB implements a number of things out of the box, including but not limited to:
* Using `Account`s as the basic owner of resoures instead of `User`.
  * I've written about this in a number of other places, blogs, etc. The best place to get started is here.
* `User`s can create multiple `Account`s (and get a private/personal `Account` by default when they sign up), and be members in multiple accounts with different roles/access levels.
  * Link to Dax tweet?
* A full invitations flow is implemented, with all of the necessary authentication, permissions, security, emails, and more.
* Robust, modern, API-driven signup, login, authentication, invitations, and more, with the frontend code to match.
  * This includes implementation of careful niceties like marking a user's email as verified if they follow a reset password link (and their email wasn't verified before).
  * Proper redirects, handling of state and errors, link invalidation, and more, using modern but also tried and true security technologies (not reinventing the wheel). To be fair, most of this is already bulit into stock Django, there are just a few convenience layers over the top and some additional security.
    * For example, BB can provide a invitation link that you can manually copy paste and send to your friend. That link will work. However, that link does not have the power to verify someone's email. At the same time, the system can send the invitation email directly, and the email link within the _system sent email_, if followed (and logged in or signed up from there), will mark the email as verified, meaning that the invited user won't have to go through the email verification flow again.
* Implementation of a design system using semantic tokens, supporting light and dark mode.
  * If you have a designer, great, your designer can change any of the Figma file variables, themeing, etc. around and there's one major section where the developers can update all of the tokens.
* ☝️ But, additionally, not reinventing the wheel when it comes to components. We're running the latest version of Chakra UI and have our design system and other modifications built on top of it.
  * There were so many different options for what to go with here. We evaluated several different options (including most if not all of the popular ones). Chakra felt like the best blend of two things:
    1. Providing a large number of powerful, accessible components out of the box, including layout components and other things that can be quite annoying to implement.
    2. Providing the end user with plenty of power and flexibility to deeply customize the components if or as needed.
  * This was a surprisingly tricky balance to find. For example, MUI had the most number of components, but then you were locked into a Material UI look and feel and it was very hard to escape that. Tailwind, on the other hand, gave full flexibility and customizability, but then you were left on your own to find a headless UI library (or multiple UI libraries) to get things like Menus, Dialogs, Popovers, etc. and then style them yourself. Chakra felt like it provided the best balance in-between those two, and we're also excited for some of the deeper customization options coming out with V3.
* Test scaffolding and coverage of the major backend sections of the codebase. You can rest confident and assured that should you want to change any of the core functionality, there are tests you can choose to change with that (or rip out if you're feeling spicy, don't recommend).
* A full guide (link) with a writeup and video walking you through adding a new feature to your application that showcases
    * Constructing a new model.
    * Writing the necessary DRF (Django REST Framework) serializers, views, filters, permissions, and more.
    * Tying ownership/creation of that model to an `Account` (instead of a `User`), but providing flexibility in who owns the data and how cascade deletion works.
    * Building the frontend list page and detail page.
    * Demonstrating things like optimistic UI, proper data handling and loading, and more.
    * Demonstrating working filtering, search, pagination, sorting, and more with the frontend collection.
    * (Coming soon) Demonstrating the full backend integration for things like metered billing on a resource.
    * (Coming soon) Showing how to prompt for subscription plans or upgrades when certain limits are met.
* ... And much more!

Anyways, thanks for reading this section. I don't expect everyone to read it, but I hope the background is helpful. If you're ready, let's (get started) (link).
