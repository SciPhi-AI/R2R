Configuring your deployment to require email verification helps keep your deployment secure, prevents unauthorized account creation,
reduces spam registrations, and ensures you have valid contact information for your users.

Currently, R2R has integrations for both [Mailersend](https://www.mailersend.com/) and [Sendgrid](https://sendgrid.com/).

## Setup
Both Mailersend and Sendgrid require registration, but do offer free tiers for evaluating their services. Create an account with your desired
provider, and generate an API key.

<Tabs>
  <Tab title="Mailersend">
  - [Create an account](https://www.mailersend.com/signup)
  - [Generate an API key](https://www.mailersend.com/help/managing-api-tokens)
  </Tab>
  <Tab title="Sendgrid">
  - [Create an account](https://twilio.com/signup)
  - [Generate an API key](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/api-keys)
  </Tab>
</Tabs>

## Creating a Template
Once you have registered for an account with your email provider, you will want to create an email template. Providers will have pre-made templates, or you can build these from scratch.

<img src="../images/cookbooks/email/mailersend.png" alt="A Mailersend welcome template." />

Once you save a template, you will want to make note of the template id. These will go into the configuration files.

## Configuration Settings
We can then configure our deployment with the templates, redirect URL (`frontend_url`), and from email.

### Configuration File

<CodeBlocks>
```toml title="mailersend.toml"
[email]
provider = "mailersend"
verify_email_template_id=""
reset_password_template_id=""
password_changed_template_id=""
frontend_url=""
from_email=""
```

```toml title="sendgrid.toml"
[email]
provider = "sendgrid"
verify_email_template_id=""
reset_password_template_id=""
password_changed_template_id=""
frontend_url=""
from_email=""
```
</CodeBlocks>

### Environment Variables
It is required to set your provider API key in your environment:

```zsh
export MAILERSEND_API_KEY=…
export SENDGRID_API_KEY=…
```
