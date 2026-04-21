import json
import logging
import os
import uuid
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from google.cloud import bigquery as bq

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BigQueryStore:
    """Handles the brand_performance.content_engagement_nested table."""
    
    def __init__(self):
        self.client = bq.Client()
        self.table_id = os.getenv("BIGQUERY_TABLE_ID")
        self.porter_table = os.getenv("PORTER_TABLE_ID")

    def insert_post(self, platform: str, content_type: str, metadata: Dict) -> str:
        """Creates the initial 'Parent' row for a new post."""
        post_id = str(uuid.uuid4())
        external_id = metadata.get("external_id", f"pending_{post_id[:8]}")
        
        row = {
            "post_id": post_id,
            "external_id": external_id,
            "platform": platform,
            "content_type": content_type,
            "publish_time": datetime.now(timezone.utc).isoformat(),
            "post_metadata": json.dumps(metadata),
            "metrics_history": [],
            "comments": []
        }
        
        errors = self.client.insert_rows_json(self.table_id, [row])
        if errors: 
            raise RuntimeError(f"BigQuery Insert Failed: {errors}")
        return post_id

    def sync_from_porter(self):
        """
        DML Query: Matches Porter's flat daily snapshots to your nested rows.
        Matches strictly by DATE to avoid duplicate entries for the same day.
        """
        query = f"""
            UPDATE `{self.table_id}` target
            SET metrics_history = ARRAY_CONCAT(metrics_history, [
                STRUCT(
                    CAST(source.likes AS INT64) as likes,
                    CAST(source.shares AS INT64) as shares,
                    CAST(source.impressions AS INT64) as impressions,
                    CAST(source.reach AS INT64) as reach,
                    TIMESTAMP(source.date) as recorded_at,
                    true as is_snapshot
                )
            ])
            FROM `{self.porter_table}` source
            WHERE target.external_id = source.post_id
            -- Date Matching Logic: Only append if this specific date is missing
            AND NOT EXISTS (
                SELECT 1 FROM UNNEST(target.metrics_history) h
                WHERE DATE(h.recorded_at) = DATE(source.date)
            )
        """
        try:
            logger.info("Starting Porter-to-Nested reconciliation...")
            query_job = self.client.query(query)
            query_job.result()
            logger.info("Sync complete: Porter data matched by date.")
        except Exception as e:
            logger.error(f"BigQuery Sync Error: {e}")

    def get_post_by_external_id(self, external_id: str) -> Optional[Dict]:
        """Finds internal post data using the platform's ID."""
        query = f"""
            SELECT post_id, platform FROM `{self.table_id}`
            WHERE external_id = @ext_id LIMIT 1
        """
        job_config = bq.QueryJobConfig(query_parameters=[
            bq.ScalarQueryParameter("ext_id", "STRING", external_id)
        ])
        results = list(self.client.query(query, job_config=job_config).result())
        return dict(results[0]) if results else None


class ZapierPublisher:
    """Unified publisher using Zapier Webhooks to bypass API complexity."""
    
    def __init__(self):
        self.webhooks = {
            "facebook": os.getenv("ZAPIER_FB_WEBHOOK"),
            "linkedin": os.getenv("ZAPIER_LI_WEBHOOK")
        }

    def publish(self, platform: str, message: str, link: str = "") -> bool:
        url = self.webhooks.get(platform)
        if not url: 
            logger.error(f"No Zapier Webhook URL defined for {platform}")
            return False
        
        payload = {"message": message, "link": link}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.ok
        except Exception as e:
            logger.error(f"Zapier Publishing Failed: {e}")
            return False


class CampaignExecutionAgent:
    def __init__(self, llm_client: Any = None):
        self.llm = llm_client
        self.store = BigQueryStore()
        self.publisher = ZapierPublisher()
        self.scheduler = BackgroundScheduler()

    def run_campaign(self, platform: str, content_bundle: Dict):
        """Manual trigger to post content and register it in BigQuery."""
        success = self.publisher.publish(
            platform=platform,
            message=content_bundle.get("body", ""),
            link=content_bundle.get("link", "")
        )
        
        if success:
            post_id = self.store.insert_post(
                platform=platform,
                content_type="status_update",
                metadata=content_bundle
            )
            logger.info(f"Campaign Live! platform={platform}, internal_id={post_id}")
            return post_id
        return None

    def start_background_sync(self, interval_hours: int = 12):
        """Starts the Scheduler to reconcile Porter Metrics every X hours."""
        self.scheduler.add_job(
            func=self.store.sync_from_porter,
            trigger="interval",
            hours=interval_hours,
            id="porter_sync_job"
        )
        self.scheduler.start()
        logger.info(f"Signalynt Sync Agent started (Interval: {interval_hours}h)")

## example on how to run this

if __name__ == "__main__":
    # Initialize Agent
    agent = CampaignExecutionAgent()
    
    # 1. Start the Background Sync (Porter -> BigQuery Nested)
    agent.start_background_sync(interval_hours=6)
    
    # 2. Example: Trigger a post
    # agent.run_campaign("linkedin", {
    #     "body": "Developing AI agents is all about the data pipeline! #Signalynt",
    #     "link": "https://xynera.com", (hosted image URL)
    # })

    # Keep the script alive for the scheduler
    try:
        import time
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        agent.scheduler.shutdown()