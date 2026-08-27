import logging

from database.db import db
from models.notification import Notification

logger = logging.getLogger(__name__)


def create_notification(union_id, created_by, title, body, category="general",
                         language="te", event_datetime=None, location=None):
    notification = Notification(
        union_id=union_id,
        created_by=created_by,
        title=title.strip(),
        body=body.strip(),
        category=category,
        language=language,
        event_datetime=event_datetime,
        location=location,
    )
    db.session.add(notification)
    db.session.commit()
    logger.info("Notification #%s created for union_id=%s by user_id=%s", notification.id, union_id, created_by)
    return notification
