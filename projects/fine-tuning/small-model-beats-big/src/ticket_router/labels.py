CATEGORIES: dict[str, str] = {
    "billing": "charges, invoices from us, refunds, plan prices, payment methods, VAT on our subscription",
    "login_access": "can't sign in, password reset, 2FA, SSO, locked accounts, inviting or removing team members",
    "bug_report": "something in the product is broken or gives a wrong result, errors, crashes",
    "feature_request": "asking for something the product doesn't do yet, or suggesting an improvement",
    "data_export": "exporting, downloading or backing up data, CSV/PDF exports, data deletion or GDPR requests",
    "integrations": "connecting to banks, Stripe, Shopify, Zapier, the API, webhooks, sync with other tools",
    "cancellation": "cancel, downgrade, pause or close the account, leaving for a competitor",
    "performance": "the app is slow, timeouts, pages loading forever, outages",
}

LABELS = list(CATEGORIES)


def category_block() -> str:
    return "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())
