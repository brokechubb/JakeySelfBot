# 💀 JAKEY BOT COMMAND REFERENCE 💀

A Discord-formatted guide to all 51 commands. Copy/paste sections as needed!

---

## 📋 QUICK REFERENCE

**51 Commands across 10 Categories:**
> 🎮 Core (6) • 🤖 AI Models (5) • 🧠 Memory (5) • 🎨 Media (3) • 👤 User/Channel (5)
> 🎰 Gambling (4) • 💰 tip.cc (9) • 📊 Queue (2) • ❓ Trivia (6) • ⚙️ Management (6)

---

## 🎮 CORE COMMANDS

```
%ping          → Check if Jakey is alive
%help          → Show user commands
%adminhelp     → Show admin commands (Admin)
%stats         → Bot statistics and uptime
%time [tz]     → Current time (e.g., %time EST)
%date [tz]     → Current date
```

---

## 🤖 AI MODEL COMMANDS (Admin Only)

```
%model              → Show current AI model
%model <name>       → Set AI model (e.g., %model gemini)
%models             → List all available AI models
%imagemodels        → List 49 artistic image styles
%aistatus           → Check AI service status
%fallbackstatus     → Show OpenRouter fallback status
```

---

## 🧠 MEMORY COMMANDS

```
%memories [query]   → Search your saved memories
%remember <type> <info>
                    → Save info about you
                    → Example: %remember favorite_team Cowboys

# Admin Only:
%clearmemories      → Delete all your memories
%memorystatus       → Memory system status
```

---

## 🎨 AI & MEDIA COMMANDS

```
%image <prompt>     → Generate an image
                    → Supports 49 styles + 9 aspect ratios
                    → Example: %image Fantasy Art a casino scene
                    → Example: %image 16:9 cinematic slot machine

%audio <text>       → Generate AI speech
                    → Example: %audio Everything is rigged bro

%analyze <url>      → Analyze an image
                    → Can also attach an image directly
```

---

## 👤 USER & CHANNEL COMMANDS

```
%friends            → List Jakey's friends

# Admin Only:
%userinfo [user]    → Get user information
%clearhistory [user] → Clear conversation history
%clearallhistory    → Clear ALL history
%clearchannelhistory → Clear channel history
%channelstats       → Channel conversation stats
```

---

## 🎰 GAMBLING & UTILITY COMMANDS

```
%rigged             → 💀 Everything's rigged bro
%wen <item>         → Bonus schedule info
                    → Example: %wen monthly, %wen stake

%keno [count]       → Generate Keno numbers (1-10)
                    → Shows visual 8x5 board

%ind_addr           → Generate random Indian address
```

---

## 💰 TIP.CC COMMANDS (Admin Only)

```
%bal / %bals        → Check tip.cc balances
%confirm            → Click Confirm on tip.cc messages
%tip @user <amt> <currency> [msg]
                    → Example: %tip @user 100 DOGE
%airdrop <amt> <currency> <duration>
                    → Example: %airdrop 1000 DOGE 5m

%transactions [limit] → Show transaction history
%tipstats           → Tip statistics and earnings
%clearstats         → Clear all tip.cc stats ⚠️
%airdropstatus      → Airdrop configuration status
```

---

## 📊 QUEUE COMMANDS (Admin Only)

```
%queuestatus        → Message queue statistics
%processqueue       → Manually process queue
```

---

## ❓ TRIVIA COMMANDS

```
%triviacats         → List trivia categories
%triviasearch <query> → Search trivia questions
                    → Example: %triviasearch Beatles

# Admin Only:
%triviastats        → Database statistics
%seedtrivia         → Seed database from external sources
%addtrivia <cat> <question> <answer>
                    → Add custom trivia
%triviatest         → Test trivia system
```

---

## ⚙️ ROLE & KEYWORD MANAGEMENT (Admin Only)

**Reaction Roles:**
```
%add_reaction_role <msg_id> <emoji> @role
%remove_reaction_role <msg_id> <emoji>
%list_reaction_roles
```

**Gender Roles:**
```
%set_gender_roles male:123,female:456,neutral:789
%show_gender_roles
```

**Keywords:**
```
%add_keyword <word>     → Add trigger keyword
%remove_keyword <word>  → Remove keyword
%list_keywords          → List all keywords
%enable_keyword <word>  → Enable keyword
%disable_keyword <word> → Disable keyword
```

**System:**
```
%clearcache         → Clear model cache
```

---

## ⏰ REMINDER EXAMPLES (Just ask Jakey!)

> "remind me in 2 hours to take a break"
> "set alarm for 8am tomorrow"
> "timer 25 minutes for pomodoro"
> "remind me next Friday at 3pm about the meeting"
> "check my reminders"
> "cancel reminder 123"

---

## 🔐 ADMIN CONFIGURATION

Set `ADMIN_USER_IDS` in your `.env` file with comma-separated Discord user IDs.

**Admin commands include:**
- All AI model management
- Memory/history clearing
- Queue management
- Role & keyword management
- tip.cc commands
- Trivia administration

---

## 💡 TIPS

1. All commands start with `%`
2. Commands work in DMs and servers (when mentioned)
3. Don't spam commands - respect rate limits
4. Check responses for success/error messages

---

*💀 Everything's rigged bro, especially Eddie's code 💀*
