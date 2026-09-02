# TerraMaster storage fixes — working plan

This branch prepares the next storage-monitoring fixes without changing `main`.

## SMART collection

- Keep SAT SMART collection as the preferred path for normal ATA disks.
- If SAT does not return a usable SMART health line, retry with permissive SCSI mode.
- Parse both ATA `SMART overall-health ... result:` and SCSI `SMART Health Status:` output.
- Do not expose a bogus SCSI temperature of `0 C`.
- System disks only expose the basic storage metrics and SMART health; ATA-only counters are not created for them.

## RAID

- Expose member devices for each array.
- Keep synchronization action and synchronization progress as separate entities.
- Report synchronization progress as `none`/`Aucune` while the array is idle, and a percentage while an operation is active.
- Identify system RAID purpose from filesystem/mount information where available rather than relying only on md device names.
- Avoid presenting mdadm spare-slot counts such as `[24/2]` as 24 physical disks expected by the NAS.

## Share pages

- Keep the existing general TerraMaster shares page.
- Add navigation back to the shares index from an individual share page.
- Add navigation back to Home Assistant.

## Tests

Cover SAT SMART, permissive SCSI SMART fallback, system-disk entity filtering, RAID members/system purpose/sync display, and share-page navigation.
