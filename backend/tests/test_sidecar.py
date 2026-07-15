from sidecar import buildParser


def testSidecarUsesDesktopLoopbackDefaults() -> None:
    options = buildParser().parse_args([])

    assert options.host == "127.0.0.1"
    assert options.port == 8765


def testSidecarAcceptsHostAndPortOverrides() -> None:
    options = buildParser().parse_args(["--host", "localhost", "--port", "9000"])

    assert options.host == "localhost"
    assert options.port == 9000


def testSidecarAcceptsParentPid() -> None:
    options = buildParser().parse_args(["--parent-pid", "1234"])

    assert options.parent_pid == 1234
