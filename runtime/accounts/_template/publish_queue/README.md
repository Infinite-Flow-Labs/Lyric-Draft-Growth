# Publish Queue Template

Queue items are created per account per day.

Expected slot layout:

```text
publish_queue/
  YYYY-MM-DD/
    01/
      post.txt
      post.jpg
      publish_job.json
```

The queue slot directory is the direct payload folder for the external `x-post` publisher.
