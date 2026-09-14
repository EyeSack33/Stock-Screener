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
itself. You should see a service named `dip-screener` on the free plan.
Click **Apply** or **Deploy**.

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

**Build succeeds but no stocks appear** - open the **Logs** tab on
Render. If you see batch failures, Yahoo is limiting requests from
Render's servers. Edit `config.yaml` on GitHub and set `limit: 100`.

**"Service suspended"** - the free plan allows 750 hours a month across
all your services. Delete any other Render services you are not using.

**Page is blank white** - it is still waking up. Give it a minute and
reload.

---

## Still want the local version?

It still works. `START-HERE.txt` covers running it on your own computer,
which is faster and has no wake-up delay. The two do not interfere, and
you can use both.
