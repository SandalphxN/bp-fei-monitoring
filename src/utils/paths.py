import os


def project_root() -> str:
    return os.getcwd()


def config_dir() -> str:
    return os.path.join(project_root(), "config")


def data_raw_dir() -> str:
    return os.path.join(project_root(), "data", "raw")


def data_processed_dir() -> str:
    return os.path.join(project_root(), "data", "processed")