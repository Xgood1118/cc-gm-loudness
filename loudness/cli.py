import argparse
import loudness as m


def main():
    ap = argparse.ArgumentParser(description="响度归一与限峰")
        ap.add_argument("--target", type=float, default=-14.0)
        ap.add_argument("--ceiling", type=float, default=-1.0)
        ap.add_argument("--out", required=True)
    a = ap.parse_args()
        print("TODO")


if __name__ == "__main__":
    main()
