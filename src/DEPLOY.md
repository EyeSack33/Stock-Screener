# Putting this online so you can open it anywhere

Right now the screener only works while your own computer is running it.
This guide moves it onto the internet, so you get a normal web address
that works from any phone or computer, anywhere.

It is free. It takes about 15 minutes. **You do not need to install
anything or use the Terminal.**

---

## What you are actually doing

Two accounts, both free:

1. **GitHub** holds the files. Think of it as a folder in the cloud.
2. **Render** reads that folder and runs the program on its own computer.

You upload the files to GitHub by dragging them in a web browser. Render
does the rest by itself.

---

## Already have an Alpaca key in use elsewhere?

Do **not** click Regenerate. That invalidates your existing pair and
every other app using it starts failing with 401 errors.

First, check your dashboard for an option to name or add a second key.
Alpaca's older documentation says regenerating replaces the single pair,
but newer guides mention naming keys, so this may have changed. If you
can create a separate named key, use that and skip the rest of this
section.

**If you cannot, read this before reusing a key.**

An Alpaca key is not read-only. The same credential that reads prices
can also place and cancel orders. This screener only ever reads, but the
key does not know that.

The page itself never exposes the key. The realistic way it leaks is
committing `config.yaml` with the key still typed into it - and that file
has to be committed for Render to work. The app now prints a loud warning
at startup if it finds a key in the file, but do not rely on noticing it.

| Approach | Data | Risk to your trading account |
|---|---|---|
| New free Alpaca account, separate email | IEX only | None |
| Reuse paper key | SIP, if paper carries your subscription | Can trade your paper account |
| Reuse live key | SIP | A leak means order access to real funds |
| Run locally only, never host it | SIP | Key never leaves your computer |

**The recommended route is a second free Alpaca account** under a
different email, paper only, never funded. Set `feed: "iex"` and the free
plan limits. You give up consolidated prices for a key that cannot cost
you anything, which is a good trade for a tool that only reads.

**On a paid plan**, config.yaml already assumes it:

| Setting | Value | Why |
|---|---|---|
| `feed` | `sip` | Every exchange combined, not just IEX, and no 15-minute delay |
| `batch_size` | `200` | Fewer, larger requests |
| `batch_pause_seconds` | `0` | Paid allows 10,000 requests a minute, so no throttling needed |
| `limit` | `0` | Scan all 503 S&P 500 companies |

One caveat: a paper account does not always carry the same data
subscription as the live account above it. If you see a 403 about the
feed, that is what happened - use the live key, or set `feed: "iex"`.

On the free plan, set `feed: "iex"`, `batch_pause_seconds: 1`, and
`limit: 100`.

---

## Part 0 - Get a free Alpaca key (5 minutes)

Yahoo blocks requests coming from hosted servers. It works fine on your
own computer and not at all on Render. Alpaca is a real API with a key,
so it does not care where you are calling from.

**1.** Go to alpaca.markets and click **Sign up**. Choose the **paper
trading** account - it is free, needs no money, and no bank details.

**2.** Once inside, find **API Keys** and click **Generate**. You get two
strings: a **Key ID** and a **Secret Key**.

**3.** Copy both somewhere safe now. The secret is shown once and cannot
be viewed again - you would have to generate a new pair.

You will paste these into Render in Part 2. They never go into the files
you upload to GitHub.

> Alpaca's free plan uses prices from the IEX exchange rather than all
> exchanges combined. For large S&P 500 companies the difference is
> usually a cent or two, which does not matter for spotting a 5% drop.

---

## Part 1 - Put the files on GitHub

**1.** Go to github.com and make an account if you do not have one.

**2.** Click the **+** in the top-right corner, then **New repository**.

**3.** Name it `dip-screener`. Leave everything else alone. Public or
Private both work - there is nothing sensitive in these files, just
settings and code. Click **Create repository**.

**4.** On the next page, click the link that says
**uploading an existing file**.

**5.** Open the folder you unzipped on your computer. Select everything
*inside* it - all the files plus the `src`, `templates`, and `data`
folders - and drag them onto the GitHub page.

> Important: drag the *contents*, not the `stock-screener` folder itself.
> GitHub should end up listing `config.yaml`, `wsgi.py`, `src` and so on
> at the top level. If you see a single `stock-screener` folder instead,
> delete the upload and try again.

**6.** Wait for the uploads to finish, scroll down, click
**Commit changes**.

You should now see all the files listed on GitHub.

---

## Part 2 - Tell Render to run it

**7.** Go to render.com and sign up. Choose **Sign up with GitHub** -
that saves you connecting the accounts later.

**8.** On your dashboard, click **New**, then **Blueprint**.

**9.** Find `dip-screener` in the list and click **Connect**. If it does
not appear, click **Configure account** and give Render permission to see
the repository.

**10.** Render reads the `render.yaml` file and fills everything in
itself. It will ask you for two values:

    ALPACA_API_KEY       <- your Key ID from Part 0
    ALPACA_API_SECRET    <- your Secret Key from Part 0

Paste them in. This is why they never need to go in the files: Render
holds them separately and hands them to the app at run time.

Then click **Apply** or **Deploy**.

**11.** Wait. The first build takes about five minutes. You can watch the
log scroll past. When it finishes you will see **Live** in green.

---

## Part 3 - Open it

**12.** At the top of the Render page is your address, something like:

    https://dip-screener.onrender.com

Open it on your phone. Add it to your home screen so it behaves like an
app: in Safari tap Share then **Add to Home Screen**; in Chrome tap the
three dots then **Add to Home screen**.

That address works from anywhere - mobile data, a work computer, a
friend's laptop.

---

## What to expect day to day

**The first visit each day is slow.** Free Render apps shut down when
nobody is looking and restart when you open the page. Expect 30 to 60
seconds to wake up, then up to another minute while it scans the market.
The page tells you it is scanning and refreshes itself, so leave it open
and it will fill in.

**After that it is quick**, and it re-checks prices every 15 minutes for
as long as you keep using it.

**The address is public.** Anyone who guessed it could see your screener.
There is nothing personal on the page, just public stock prices, so this
is a fair trade for keeping things simple.

**Nothing is saved.** Each scan replaces the last. Come back tomorrow and
you get fresh numbers, not yesterday's.

---

## Changing settings later

Edit `config.yaml` directly on GitHub: click the file, click the pencil
icon, make your change, click **Commit changes** at the bottom. Render
notices and redeploys by itself within a few minutes.

The settings worth touching:

| Setting | What it does |
|---|---|
| `limit` | How many stocks to scan. 200 by default. 0 scans all 503 but makes every wake-up slower. |
| `buy_threshold` | Minimum score to show up. 60 by default. Lower it to see more names. |
| `dip_full_scale_pct` | The drop size that scores best. 5.0 means a 5% drop is ideal. |
| `max_results` | How many rows the page shows. |

---

## If something goes wrong

**Build fails immediately** - the files are probably nested inside an
extra folder. Check that `render.yaml` sits at the top level of your
GitHub repository, not inside `stock-screener/`.

**"Alpaca needs api_key and api_secret"** - the environment variables did
not save. On Render open the service, click **Environment**, and check
both are there with no stray spaces.

**"Alpaca rejected your key"** - the Key ID and Secret are from different
generated pairs, or the secret was truncated when copied. Generate a
fresh pair and paste both again.

**Stuck on "Scanning the market"** - add `/debug` to the end of your
Render address, like `https://dip-screener.onrender.com/debug`. It gives
you a plain-text report in the browser: how long the app has been alive,
whether any scan has ever finished, and a live test of the Yahoo
connection. Read it before changing anything.

  - "Result: EMPTY" means Yahoo is blocking this server.
  - "App running for" resetting to a few seconds on every reload means
    the app is restarting instead of scanning.
  - "Result: OK" plus a stalled scan means it is a memory or restart
    problem, not a data problem.

The page also shows which batch it is
working on. If that number is not climbing, open the **Logs** tab on
Render. Lines like `got 0, missed 100` mean Yahoo is refusing requests
from Render's servers. Edit `config.yaml` on GitHub and set
`limit: 50`, `batch_size: 25`, `batch_pause_seconds: 3`.

If the log keeps showing the startup banner over and over, the app is
restarting rather than scanning - that is Render's free plan running out
of memory. Lower `limit` to 50.

**"Service suspended"** - the free plan allows 750 hours a month across
all your services. Delete any other Render services you are not using.

**Page is blank white** - it is still waking up. Give it a minute and
reload.

---

## Still want the local version?

It still works. `START-HERE.txt` covers running it on your own computer,
which is faster and has no wake-up delay. The two do not interfere, and
you can use both.
