import prefect.filesystems


def get_storage_file_system(extended_block_name: str) -> prefect.filesystems.Block:
    block_type_slug, name = extended_block_name.partition("/")[::2]
    if block_type_slug == "remote-file-system":
        file_system = prefect.filesystems.RemoteFileSystem.load(name)
    else:
        raise RuntimeError(
            f"File systems of type {block_type_slug!r} are not supported."
        )
    return file_system
