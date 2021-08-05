#!/usr/bin/env python
import argparse
import textwrap
import curses
import ROOT

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description="Browse MC records in SCT files.",
    epilog=textwrap.dedent(
        """
Interactive controls:
  - Right: next event
  - Left: previous event
  - Down: scroll down
  - Up: scroll up
  - Page Down: scroll page down
  - Page Up: scroll page up
  - q: quit
  - g: goto event index (0 is first event)

"""
    ),
)
parser.add_argument("input_file", help="SCT file with MC record")
args = parser.parse_args()


root_file = ROOT.TFile.Open(args.input_file)
sct = root_file.sct
if not hasattr(sct, "mc_trk_len"):
    raise SystemExit("error: SCT does not contain a MC record")

nentries = sct.GetEntries()
pdg_db = ROOT.TDatabasePDG.Instance()


def is_long_lived(pid):
    pid = abs(pid)
    return pid in (
        11,
        12,
        13,
        14,
        16,
        22,
        130,
        211,
        310,
        321,
        2112,
        2212,
        3112,
        3122,
        3312,
        3322,
        3334,
    )


def get_prompt(k, kmax, pid, imot):
    assert k >= 0
    result = k
    while True:
        k = imot[k]
        if k == -1:
            break
        assert k >= 0 and k < kmax
        if is_long_lived(pid[k]):
            result = k
    return result


final_state_mask = 1 << 0
track_associated_mask = 1 << 2
long_lived_mask = 1 << 3
prompt_mask = 1 << 4


class Node(dict):
    def __init__(self, pid, energy, flag):
        dict.__init__(self)
        self.pid = pid
        self.energy = energy
        self.flag = flag

    def __lt__(self, other):
        return self.energy < other.energy


def get_event_tree(sct):
    def energy(i):
        px = sct.mc_trk_px[i]
        py = sct.mc_trk_py[i]
        pz = sct.mc_trk_pz[i]
        m = sct.mc_trk_m[i]
        return (px * px + py * py + pz * pz + m * m) ** 0.5

    energies = [energy(i) for i in range(sct.mc_trk_len)]

    # mark particles as prompt and/or long-lived
    flags = [ord(sct.mc_trk_flag[i]) for i in range(sct.mc_trk_len)]
    for ipart in range(sct.mc_trk_len):
        pid = sct.mc_trk_pid[ipart]
        flag = flags[ipart]
        if is_long_lived(pid):
            flag |= long_lived_mask
        if flag & final_state_mask:
            flags[
                get_prompt(ipart, sct.mc_trk_len, sct.mc_trk_pid, sct.mc_trk_imot)
            ] |= prompt_mask

    root = Node(None, None, None)
    esum_prompt = 0.0
    for ipart in range(sct.mc_trk_len):
        if flags[ipart] & prompt_mask:
            esum_prompt += energies[ipart]
        chain = []
        imot = ipart
        while imot != -1:
            chain.append(imot)
            imot = sct.mc_trk_imot[imot]
        node = root
        for i in reversed(chain):
            if i not in node:
                node[i] = Node(sct.mc_trk_pid[i], energies[i], flags[i])
            node = node[i]
    esum_prompt /= sct.mc_vtx_len

    class count_visitor:
        n = 0

        def __call__(self, node):
            if node.pid is not None:
                self.n += 1
            for child in node.values():
                self(child)

    cv = count_visitor()
    cv(root)
    assert cv.n == sct.mc_trk_len

    return root, cv.n, esum_prompt


def draw_event(stdscr, root, ievent, npart, esum_prompt, offset):
    stdscr.clear()
    if offset > 0:
        stdscr.addstr(0, 0, "  ^^^^^^^^")
    else:
        stdscr.addstr(
            0,
            0,
            "event %i: %i particles, esum[prompt]/Npv %.2f TeV"
            % (ievent, npart, esum_prompt / 1e6),
        )

    class print_visitor:
        iy = 1

        def __call__(self, node, ix=0):
            if self.iy - offset == curses.LINES - 1:
                stdscr.addstr(self.iy - offset, 0, "  vvvvvvvv")
                return
            if node.pid is not None:
                if self.iy - offset > 0:
                    pdb_entry = pdg_db.GetParticle(node.pid)
                    if pdb_entry:
                        name = pdb_entry.GetName()
                    else:
                        if node.pid // 1000000000 == 1:
                            pid = node.pid - 1000000000
                            z = pid // 10000
                            pid -= z * 10000
                            a = pid / 10
                            name = "Nucleus(%i,%i)" % (z, a)
                            print(name, node.pid)
                        else:
                            name = "Unknown(%i)" % node.pid
                    sflag = ""
                    if node.flag & final_state_mask:
                        sflag += "[final]"
                    if node.flag & track_associated_mask:
                        sflag += "[associated]"
                    if node.flag & prompt_mask:
                        sflag += "[prompt]"
                    stdscr.addstr(
                        self.iy - offset,
                        ix,
                        "%s %.1f GeV/c %s" % (name, node.energy / 1e3, sflag),
                    )
                self.iy += 1
            for child in reversed(sorted(node.values())):
                self(child, ix + 3)

    pv = print_visitor()
    pv(root)
    stdscr.refresh()


def main(stdscr):
    stdscr.clear()
    ievent = 0
    offset = 0
    sct.GetEntry(ievent)
    tree, npart, esum_prompt = get_event_tree(sct)
    draw_event(stdscr, tree, ievent, npart, esum_prompt, offset)

    while True:
        c = stdscr.getch()
        if c == curses.KEY_RIGHT:
            if ievent == nentries:
                continue
            ievent += 1
            offset = 0
            sct.GetEntry(ievent)
            tree, npart, esum_prompt = get_event_tree(sct)
        elif c == curses.KEY_LEFT:
            if ievent == 0:
                continue
            ievent -= 1
            offset = 0
            sct.GetEntry(ievent)
            tree, npart, esum_prompt = get_event_tree(sct)
        elif c == curses.KEY_DOWN:
            offset += 1
        elif c == curses.KEY_UP:
            if offset == 0:
                continue
            offset -= 1
        elif c == curses.KEY_HOME:
            offset = 0
        elif c == curses.KEY_PPAGE:
            if offset == 0:
                continue
            offset = max(0, offset - (curses.LINES - 3))
        elif c == curses.KEY_NPAGE:
            offset += curses.LINES - 3
        elif c == ord("q"):
            break
        elif c == ord("g"):
            stdscr.addstr(0, 0, "go to: " + " " * (curses.COLS - 7))
            stdscr.move(0, 7)
            stdscr.refresh()
            goto = None
            while True:
                key = stdscr.getkey()
                try:
                    n = int(key)
                    if goto is None:
                        goto = 0
                    goto = goto * 10 + n
                    stdscr.addstr(key)
                except:  # noqa
                    break
            if goto is not None:
                offset = 0
                ievent = goto
                sct.GetEntry(ievent)
                tree, npart, esum_prompt = get_event_tree(sct)

        draw_event(stdscr, tree, ievent, npart, esum_prompt, offset)


curses.wrapper(main)
