# MamaStoria UAT Checklist

# Version: 1.0

# Date: 2026-01-10

## UAT Environment

| Item           | Value                                                            |
| -------------- | ---------------------------------------------------------------- |
| Backend URL    | https://nanobanana-backend-1089713441636.asia-southeast2.run.app |
| Frontend URL   | https://app.mamastoria.com                                       |
| Tester Name    |                                                                  |
| Test Date      |                                                                  |
| Device/Browser |                                                                  |

---

## 1. AUTHENTICATION TESTS

| ID       | Test Case            | Steps                                                | Expected Result                     | Status            | Notes |
| -------- | -------------------- | ---------------------------------------------------- | ----------------------------------- | ----------------- | ----- |
| AUTH-001 | Register new account | 1. Open app 2. Tap Register 3. Fill form 4. Submit   | Account created, redirected to home | [ ] Pass [ ] Fail |       |
| AUTH-002 | Login with email     | 1. Open app 2. Enter email/password 3. Tap Login     | Login success, see home screen      | [ ] Pass [ ] Fail |       |
| AUTH-003 | Login with Google    | 1. Tap "Login with Google" 2. Select Google account  | Login success                       | [ ] Pass [ ] Fail |       |
| AUTH-004 | Logout               | 1. Go to Profile 2. Tap Logout                       | Redirected to login screen          | [ ] Pass [ ] Fail |       |
| AUTH-005 | Forgot Password      | 1. Tap Forgot Password 2. Enter email 3. Check email | Receive reset email                 | [ ] Pass [ ] Fail |       |
| AUTH-006 | Session persistence  | 1. Login 2. Close app 3. Reopen                      | Still logged in                     | [ ] Pass [ ] Fail |       |

---

## 2. COMIC CREATION TESTS

| ID         | Test Case                          | Steps                                                                                     | Expected Result                   | Status            | Time    | Notes |
| ---------- | ---------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------- | ----------------- | ------- | ----- |
| CREATE-001 | Create comic (Ghibli + Fantasi)    | 1. Tap Create 2. Enter story 3. Select Style: Ghibli 4. Select Genre: Fantasi 5. Generate | Comic generated with Ghibli style | [ ] Pass [ ] Fail | \_\_\_s |       |
| CREATE-002 | Create comic (Manga + Petualangan) | Same as above with Manga style                                                            | Comic has Manga visual style      | [ ] Pass [ ] Fail | \_\_\_s |       |
| CREATE-003 | Create comic (Cartoon 3D + Komedi) | Same as above with 3D style                                                               | Comic has 3D cartoon look         | [ ] Pass [ ] Fail | \_\_\_s |       |
| CREATE-004 | Story pendek (50 kata)             | Enter short story                                                                         | Generates successfully            | [ ] Pass [ ] Fail | \_\_\_s |       |
| CREATE-005 | Story panjang (500+ kata)          | Enter long story                                                                          | Generates successfully            | [ ] Pass [ ] Fail | \_\_\_s |       |
| CREATE-006 | Cancel during generation           | 1. Start generate 2. Press back                                                           | Gracefully cancelled              | [ ] Pass [ ] Fail |         |       |
| CREATE-007 | Network interruption               | 1. Start generate 2. Turn off WiFi                                                        | Shows error, can retry            | [ ] Pass [ ] Fail |         |       |

---

## 3. COMIC VIEWING TESTS

| ID       | Test Case         | Steps                           | Expected Result                  | Status            | Notes |
| -------- | ----------------- | ------------------------------- | -------------------------------- | ----------------- | ----- |
| VIEW-001 | Browse comics     | 1. Open Explore tab 2. Scroll   | Comics load, pagination works    | [ ] Pass [ ] Fail |       |
| VIEW-002 | View comic detail | 1. Tap on comic                 | Show detail page with panels     | [ ] Pass [ ] Fail |       |
| VIEW-003 | Panel viewer      | 1. Open comic 2. Swipe panels   | Smooth swipe, all panels visible | [ ] Pass [ ] Fail |       |
| VIEW-004 | Play video        | 1. Open comic 2. Tap play video | Video plays with audio           | [ ] Pass [ ] Fail |       |
| VIEW-005 | Like comic        | 1. Tap heart icon               | Like count increases             | [ ] Pass [ ] Fail |       |
| VIEW-006 | Unlike comic      | 1. Tap heart again              | Like count decreases             | [ ] Pass [ ] Fail |       |
| VIEW-007 | Share comic       | 1. Tap share 2. Select platform | Share menu opens                 | [ ] Pass [ ] Fail |       |
| VIEW-008 | Download PDF      | 1. Tap download PDF             | PDF downloads/opens              | [ ] Pass [ ] Fail |       |

---

## 4. USER PROFILE TESTS

| ID          | Test Case            | Steps                                    | Expected Result           | Status            | Notes |
| ----------- | -------------------- | ---------------------------------------- | ------------------------- | ----------------- | ----- |
| PROFILE-001 | View my profile      | 1. Tap Profile tab                       | Shows profile info        | [ ] Pass [ ] Fail |       |
| PROFILE-002 | Edit profile         | 1. Tap Edit 2. Change name 3. Save       | Profile updated           | [ ] Pass [ ] Fail |       |
| PROFILE-003 | View my comics       | 1. Tap "Komik Saya"                      | Shows user's comics       | [ ] Pass [ ] Fail |       |
| PROFILE-004 | View drafts          | 1. Tap "Draft"                           | Shows draft comics        | [ ] Pass [ ] Fail |       |
| PROFILE-005 | Follow user          | 1. Open other user profile 2. Tap Follow | Following count increases | [ ] Pass [ ] Fail |       |
| PROFILE-006 | Unfollow user        | 1. Tap Unfollow                          | Following count decreases | [ ] Pass [ ] Fail |       |
| PROFILE-007 | Upload profile photo | 1. Tap avatar 2. Select image            | Photo updated             | [ ] Pass [ ] Fail |       |

---

## 5. NOTIFICATION TESTS

| ID        | Test Case                   | Steps                     | Expected Result           | Status            | Notes |
| --------- | --------------------------- | ------------------------- | ------------------------- | ----------------- | ----- |
| NOTIF-001 | Comic complete notification | 1. Generate comic 2. Wait | Receive push notification | [ ] Pass [ ] Fail |       |
| NOTIF-002 | New follower notification   | 1. Another user follows   | Receive notification      | [ ] Pass [ ] Fail |       |
| NOTIF-003 | In-app notification list    | 1. Tap notification bell  | Shows notification list   | [ ] Pass [ ] Fail |       |
| NOTIF-004 | Mark as read                | 1. Tap notification       | Marked as read            | [ ] Pass [ ] Fail |       |

---

## 6. PERFORMANCE METRICS

| Metric                   | Target  | Actual    | Status            |
| ------------------------ | ------- | --------- | ----------------- |
| App launch time          | < 3s    | \_\_\_s   | [ ] Pass [ ] Fail |
| Comic list load          | < 1s    | \_\_\_s   | [ ] Pass [ ] Fail |
| Comic detail load        | < 500ms | \_\_\_ms  | [ ] Pass [ ] Fail |
| Panel swipe lag          | None    |           | [ ] Pass [ ] Fail |
| Video buffer time        | < 2s    | \_\_\_s   | [ ] Pass [ ] Fail |
| Comic generation (total) | < 5 min | \_\_\_min | [ ] Pass [ ] Fail |
| Script generation        | < 30s   | \_\_\_s   | [ ] Pass [ ] Fail |
| Image generation         | < 2 min | \_\_\_s   | [ ] Pass [ ] Fail |
| Video generation         | < 3 min | \_\_\_s   | [ ] Pass [ ] Fail |

---

## 7. STYLE VALIDATION (All 16 Styles)

| Style ID | Style Name        | Visual Correct? | Status |
| -------- | ----------------- | --------------- | ------ |
| 1        | Realistic         | [ ] Yes [ ] No  |        |
| 2        | Cartoon           | [ ] Yes [ ] No  |        |
| 3        | Anime             | [ ] Yes [ ] No  |        |
| 4        | Manga B&W         | [ ] Yes [ ] No  |        |
| 5        | Webtoon           | [ ] Yes [ ] No  |        |
| 6        | Ghibli            | [ ] Yes [ ] No  |        |
| 7        | Watercolor        | [ ] Yes [ ] No  |        |
| 8        | Pixel Art         | [ ] Yes [ ] No  |        |
| 9        | Comic Book        | [ ] Yes [ ] No  |        |
| 10       | Chibi             | [ ] Yes [ ] No  |        |
| 11       | Pastel Soft       | [ ] Yes [ ] No  |        |
| 12       | Pop Art           | [ ] Yes [ ] No  |        |
| 13       | Fantasy Painting  | [ ] Yes [ ] No  |        |
| 14       | Modern Minimalist | [ ] Yes [ ] No  |        |
| 15       | Retro American    | [ ] Yes [ ] No  |        |
| 16       | Cartoon 3D        | [ ] Yes [ ] No  |        |

---

## 8. GENRE VALIDATION (All 12 Genres)

| Genre ID | Genre Name          | Rules Applied? | Status |
| -------- | ------------------- | -------------- | ------ |
| 1        | Fiksi Keluarga      | [ ] Yes [ ] No |        |
| 2        | Slice of Life       | [ ] Yes [ ] No |        |
| 3        | Komedi              | [ ] Yes [ ] No |        |
| 4        | Petualangan         | [ ] Yes [ ] No |        |
| 5        | Fantasi             | [ ] Yes [ ] No |        |
| 6        | Edukasi             | [ ] Yes [ ] No |        |
| 7        | Fabel               | [ ] Yes [ ] No |        |
| 8        | Religius            | [ ] Yes [ ] No |        |
| 9        | Motivasi            | [ ] Yes [ ] No |        |
| 10       | Super Hero          | [ ] Yes [ ] No |        |
| 11       | Supranatural        | [ ] Yes [ ] No |        |
| 12       | Kuliner & Lifestyle | [ ] Yes [ ] No |        |

---

## SIGN OFF

| Role          | Name | Signature | Date |
| ------------- | ---- | --------- | ---- |
| Tester        |      |           |      |
| Developer     |      |           |      |
| Product Owner |      |           |      |

---

## ISSUES FOUND

| Issue ID | Description | Severity                                 | Steps to Reproduce | Screenshot |
| -------- | ----------- | ---------------------------------------- | ------------------ | ---------- |
|          |             | [ ] Critical [ ] High [ ] Medium [ ] Low |                    |            |
|          |             | [ ] Critical [ ] High [ ] Medium [ ] Low |                    |            |
|          |             | [ ] Critical [ ] High [ ] Medium [ ] Low |                    |            |
