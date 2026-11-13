import os
import tempfile

# Tests schreiben nie auf einen echten Desktop
os.environ.setdefault("SOCIAL_MEDIA_FOLDER", os.path.join(tempfile.gettempdir(), "sma-tests"))
