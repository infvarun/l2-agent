Title: Balance Table Mismatch

Alert Type: BALANCE_DISCREPANCY

Summary:
Investigate a row‑count or amount mismatch between `balance_hdr` and `balance_snap`.

Steps:
1. Verify record counts:
   SQL: SELECT COUNT(*) FROM balance_hdr;
2. Compare balance sums:
   SQL:
   SELECT SUM(amount) FROM balance_hdr
   UNION ALL
   SELECT SUM(amount) FROM balance_snap;
3. If variance > 5 %, raise DBA ticket and re‑run ETL.