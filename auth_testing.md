# Auth Testing Playbook — BEATCUT

## Step 1: MongoDB Verification
```
mongosh
use test_database
db.users.find({role: "admin"}).pretty()
db.users.findOne({role: "admin"}, {password_hash: 1})
```
Verify: bcrypt hash starts with `$2b$`, index unique on users.email.

## Step 2: API Testing (JWT)
```
curl -c cookies.txt -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" -d '{"email":"admin@beatcut.fr","password":"Admin123!"}'
curl -b cookies.txt http://localhost:8001/api/auth/me
```
Login returns the user object and sets `access_token` cookie. `/me` returns same user.

## Step 3: Google Auth test session (Emergent)
```
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({user_id: userId, email: 'test.user.' + Date.now() + '@example.com', name: 'Test User', auth_provider: 'google', subscription: null, created_at: new Date().toISOString()});
db.user_sessions.insertOne({user_id: userId, session_token: sessionToken, expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(), created_at: new Date().toISOString()});
print('Session token: ' + sessionToken);
"
```
Then: `curl -H "Authorization: Bearer SESSION_TOKEN" http://localhost:8001/api/auth/me`

## Step 4: Subscription flow
1. Login as demo@beatcut.fr / Demo1234!
2. POST /api/payments/checkout {"origin_url":"https://pro-mailer-2.preview.emergentagent.com"} → returns Stripe URL + session_id
3. (Test mode) GET /api/payments/status/{session_id} polls status; on paid → user.subscription.status=active, 30 days
4. To force PRO for testing: db.users.updateOne({email:'demo@beatcut.fr'},{$set:{subscription:{status:'active',started_at:new Date().toISOString(),current_period_end:new Date(Date.now()+30*864e5).toISOString()}}})
5. POST /api/subscription/cancel → status becomes 'canceled', access kept until period end (is_pro stays true, cancel_at_period_end true)

## Browser testing
- Set cookie `access_token` (JWT) or `session_token` then load /dashboard
- Studio page (/studio) embeds /studio.html in iframe; studio fetches /api/auth/me with credentials to know is_pro (watermark logic)
