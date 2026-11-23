# Written Answers

## Question 1

> A service stores user names in users.display_name. A proposed release introduces
> users.full_name, changes all application reads and writes to the new column, and drops
> display_name in the same deployment. The service uses rolling deployment, so old and new
> application instances run concurrently. The release must also support rollback. Explain why
> this release can fail and propose a safe sequence of database and application changes.

**Answer one:** Rolling deployment creates a period when old instances still read and write display_name.It may cause data inconsistent since the old instance writes display_name and the new instance writes full_name. For the new instance who reads the old data, it will write nullable value. Also, dropping the old column breaks those instances and makes rollback to the old version impossible.

**The expected sequence:**

1. Deploy a complibility version that display_name, and writes both columns in one transaction.
2. Backfill full_name from display_name in batches.
3. Deploy the reading full_name version, and also write both columns.
4. Only after the new version is stable, stop writing both columns and drop display_name column.

## Question 2

> Certificate details are cached for 60 seconds. Request A misses the cache and reads ACTIVE
> from the database. Before A writes to the cache, request B revokes the certificate, commits
> the database transaction, and deletes the cache entry. A then writes its stale ACTIVE value
> into the cache. A colleague proposes reducing the cache TTL to five seconds. Explain why this
> does not fix the problem. Redesign the read and revocation paths so that any read starting
> after B returns success cannot receive the stale ACTIVE value.

**Answer 2:** A short TTL does not solve this problem. A can also write cache after B deletes and requests will also read the wrong value. To solve this problem, use a distributed lock. A reads the data, acquires the lock and then writes to the cache. If B wants to delete the cache entry, it will wait for the lock released.

## Question 3

> Service A has 50 request workers. Every request to its /report endpoint calls Service B with a
> 100 ms timeout and up to three retries. Traffic to /report remains at 1,000 requests per
> second. B's latency suddenly rises from 20 ms to 2 seconds, and unrelated endpoints on A
> soon stop responding. Explain the chain of failure, including the effect of retries. Redesign
> /report so unrelated endpoints remain available, and state what /report should return when
> B is unhealthy.

**Answer 3:** When B takes 2 second, each attempt may occupy a thread for more than 300ms (3 * 100ms timeout + retry delay). As for 1000 request per second, it needs more than 300 workers. Therefore, other requests can not get workers. When B is unhealthy, /report should fail fast with Service available or return a default value.
