import py_compile
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parent

for launch_file in [
    root / 'launch' / 'display.launch.py',
    root / 'launch' / 'gazebo_ros_ign.launch.py',
    root / 'launch' / 'gazebo_ros_gz.launch.py',
]:
    py_compile.compile(str(launch_file), doraise=True)
    print(f'PY OK: {launch_file.relative_to(root)}')

for xml_file in [
    root / 'urdf' / 'object_lifter_preview.urdf',
    root / 'worlds' / 'object_lifter_empty.sdf',
    root / 'package.xml',
]:
    ET.parse(xml_file)
    print(f'XML OK: {xml_file.relative_to(root)}')
