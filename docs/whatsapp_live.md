# Live WhatsApp test (Meta WhatsApp Business Cloud API)

The same agent team, safety layer and approvals as the demo, on real WhatsApp. Patients write to the clinic
number; the assistant answers on WhatsApp; the therapist watches and approves in the web app at
`http://localhost:8000/?session=live`.

**Test phones only.** Only numbers in `WHATSAPP_ALLOWED` get answers; anyone else is ignored. Messages
go to the model through the course key, so real patients must not write to it during the test.

## 1. Meta app (10 minutes, in the browser)

1. Go to <https://developers.facebook.com/apps> → **Create app** → use case **Other** → type **Business** →
   name it "PhysioTeam test".
2. In the app, **Add product → WhatsApp → Set up**. Meta creates a business portfolio and gives you a
   free **test phone number** to act as the clinic.
3. **WhatsApp → API Setup**:
   - copy the **Temporary access token** (valid 24 h) → `WHATSAPP_TOKEN`
   - copy the **Phone number ID** → `WHATSAPP_PHONE_NUMBER_ID`
   - under **To**, add each test phone (yours, the therapist's) and confirm the code WhatsApp sends.
4. **App settings → Basic → App secret → Show** → `WHATSAPP_APP_SECRET`.

### Using your own phone as the clinic number (optional, later)

Under **API Setup → Add phone number** you can register a real number instead of Meta's test number.
That number must not be in use on WhatsApp (delete its WhatsApp account first). After that the phone
can't open those chats in the WhatsApp app: the therapist reads and answers them in Clinic Messages,
which is the product's design. Start with the test number; switch once the loop works.

## 2. Keys (in the course `.env`, never in the repo)

```
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_APP_SECRET=...
WHATSAPP_VERIFY_TOKEN=pick-any-long-random-string
WHATSAPP_ALLOWED=+52 55 1111 2222,+52 55 3333 4444
```

Restart the server after editing `.env`.

## 3. A public address for the webhook

Meta must reach your laptop over HTTPS. A Cloudflare quick tunnel needs no account:

```
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:8000
```

It prints an address like `https://something-random.trycloudflare.com` (new each time you start it).
On Render, use the service URL instead.

## 4. Point Meta at it

**WhatsApp → Configuration → Webhook → Edit**:
- Callback URL: `https://<your tunnel>/webhook/whatsapp`
- Verify token: the same `WHATSAPP_VERIFY_TOKEN`
- **Verify and save**, then **Manage → subscribe to `messages`**.

## 5. Test

1. From a test phone, send "Hi" to the clinic's test number. The reply starts with the AI disclosure.
2. Open `http://localhost:8000/?session=live` → Therapist → Clinic Messages: the conversation is there.
   Approvals (bookings, charges) wait in Approvals; you can also answer as Lic. Ana yourself
   ("Reply as Lic. Ana"), and it goes out on WhatsApp.
3. Try: prices, booking a time, cancelling, a medication question, "my calf is swollen and hot".

Limits of the test: text messages only (photos get a polite "text only for now"); the clinic agenda is
the demo's fictional week; replies are free inside WhatsApp's 24-hour window after the patient writes.
