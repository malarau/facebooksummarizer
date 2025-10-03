import logging

app_logger = logging.getLogger("facebook_scraper")
app_logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
# Updated format: Adds %(filename)s for the source file, %(funcName)s for the function, and %(lineno)d for the line number
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d in %(funcName)s - %(message)s"
))
app_logger.addHandler(handler)