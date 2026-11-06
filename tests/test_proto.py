"""Los contratos del Anexo A compilan y exponen los servicios y RPC previstos."""

from dfsha.v1 import common_pb2, datanode_pb2, datanode_pb2_grpc, metadata_pb2, metadata_pb2_grpc

METADATA_RPCS = {
    "Authenticate", "CreateUser",
    "ListDirectory", "GetFileInfo", "CreateDirectory", "DeleteDirectory", "DeleteFile", "MovePath",
    "OpenFile", "GetBlockLocations", "LockBlocks", "UpdateLease", "UnlockBlocks",
    "AllocateBlocks", "CommitFile", "AbortFile",
    "RegisterDataNode", "ReportHeartbeat", "ReportBlocks", "ReportBlockReceived",
    "ReportCorruptReplica",
}  # fmt: skip


def test_metadata_service_has_all_rpcs() -> None:
    service = metadata_pb2.DESCRIPTOR.services_by_name["MetadataService"]
    assert {method.name for method in service.methods} == METADATA_RPCS
    assert hasattr(metadata_pb2_grpc, "MetadataServiceStub")


def test_datanode_service_streams_blocks() -> None:
    service = datanode_pb2.DESCRIPTOR.services_by_name["DataNodeService"]
    write_block = service.methods_by_name["WriteBlock"]
    read_block = service.methods_by_name["ReadBlock"]
    assert write_block.client_streaming and not write_block.server_streaming
    assert read_block.server_streaming and not read_block.client_streaming
    assert hasattr(datanode_pb2_grpc, "DataNodeServiceStub")


def test_all_packages_are_dfsha_v1() -> None:
    for module in (common_pb2, metadata_pb2, datanode_pb2):
        assert module.DESCRIPTOR.package == "dfsha.v1"


def test_enums_start_with_unspecified() -> None:
    for enum in common_pb2.DESCRIPTOR.enum_types_by_name.values():
        assert enum.values_by_number[0].name == f"{_to_upper_snake(enum.name)}_UNSPECIFIED"


def test_block_location_round_trip() -> None:
    location = common_pb2.BlockLocation(
        block_index=3,
        block_id="b-0001",
        block_sha256=bytes(32),
        size_bytes=16 * 1024 * 1024,
        datanode_addrs=["datanode-2:50052", "datanode-4:50052", "datanode-5:50052"],
    )
    decoded = common_pb2.BlockLocation.FromString(location.SerializeToString())
    assert decoded == location
    assert decoded.datanode_addrs[0] == "datanode-2:50052"


def _to_upper_snake(name: str) -> str:
    return "".join(f"_{char}" if char.isupper() and index else char for index, char in enumerate(name)).upper()
