from __future__ import annotations
import struct
from dataclasses import dataclass

@dataclass
class NtfsBoot:
    bytes_per_sector: int
    sectors_per_cluster: int
    mft_lcn: int
    mftmirr_lcn: int
    clusters_per_mft_record: int # signed char spec
    clusters_per_index_buffer: int
    total_sectors: int
    @property
    def sector_size(self) -> int:
        return self.bytes_per_sector


    @property
    def cluster_size(self) -> int:
        return self.bytes_per_sector * self.sectors_per_cluster


    @property
    def mft_record_size(self) -> int:
        c = self.clusters_per_mft_record
        if c < 0:
            return 1 << (-c) # 2^|c| bytes
        return c * self.cluster_size


    def lcn_to_off(self, lcn: int) -> int:
        return lcn * self.cluster_size
def parse_boot_sector(bs: bytes) -> NtfsBoot:
    if len(bs) < 90:
        raise ValueError("Boot sector too small")
    o = 11
    bytes_per_sector = struct.unpack_from('<H', bs, o)[0]
    sectors_per_cluster = bs[o+2]
    total_sectors = struct.unpack_from('<Q', bs, 40)[0]
    mft_lcn = struct.unpack_from('<Q', bs, 48)[0]
    mftmirr_lcn = struct.unpack_from('<Q', bs, 56)[0]
    clusters_per_mft_record = struct.unpack_from('<b', bs, 64)[0]
    clusters_per_index_buffer = struct.unpack_from('<b', bs, 68)[0]
    if bs[3:11] != b"NTFS ":
        # Vẫn cho phép tiếp tục: đôi khi boot backup… nhưng nên cảnh báo
        pass
    return NtfsBoot(
    bytes_per_sector=bytes_per_sector,
    sectors_per_cluster=sectors_per_cluster,
    mft_lcn=mft_lcn,
    mftmirr_lcn=mftmirr_lcn,
    clusters_per_mft_record=clusters_per_mft_record,
    clusters_per_index_buffer=clusters_per_index_buffer,
    total_sectors=total_sectors,
    )