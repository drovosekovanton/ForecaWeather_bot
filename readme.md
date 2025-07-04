Simple parsing bot for Foreca weather. Current day, next day, ten-days forecast. Just one city, for personal use only.

Create python virtual environment with all prerequisites. Put token for your bot and set of admin's ids to config.py (must be laid alongside bot.py) like this:

```python
TOKEN = 'your_own_token'
ADMINS = {777888999}
```

Edit the next url paths for desired location in bot.py:

`THIS_DAY_URL`
`NEXT_DAY_URL`
`TEN_DAY_URL`

Edit paths in forecaweather-bot.service and put it in /usr/lib/systemd/system/ (Ubuntu distros).

Then:
- systemctl enable forecaweather-bot
- systemctl start forecaweather-bot

Optionally you can use
- systemctl status forecaweather-bot
- systemctl restart forecaweather-bot
- systemctl stop forecaweather-bot

---
The python script is hardcoded to russian, but I think you can handle it.