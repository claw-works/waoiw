from setuptools import setup, find_packages

setup(
    name="waoiw",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "mss",
        "Pillow",
        "pytesseract",
        "opencv-python",
        "numpy",
        "pydirectinput",
        "pydantic",
        "pydantic-settings",
        "rich",
        "anthropic",
        "keyboard",
    ],
    python_requires=">=3.11",
)
