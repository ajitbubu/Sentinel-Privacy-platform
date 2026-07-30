// Run: mongosh consent_db init_collections.js
db.createCollection("audit_history");
db.audit_history.createIndex({ entity_id: 1, timestamp: -1 });
db.audit_history.createIndex({ timestamp: -1 });

db.createCollection("event_stream", { capped: true, size: 1073741824, max: 1000000 });
db.event_stream.createIndex({ event_type: 1, timestamp: -1 });

db.createCollection("webhook_delivery_history");
db.webhook_delivery_history.createIndex({ created_at: 1 }, { expireAfterSeconds: 2592000 });
