/*!
 * Veltrix — JS Edition (web worker build for MATIN CHESS Android)
 * A compact UCI chess engine: alpha-beta + quiescence, tapered PST eval.
 * Derived from the Veltrix project (C++ UCI engine) by the same author.
 *
 * Copyright (C) 2026 Veltrix Project / amirmhmdglstan-stack
 * License: GPL-3.0-or-later
 */
(function (global) {
"use strict";

var FILES = "abcdefgh";
var VAL = { P: 100, N: 320, B: 330, R: 500, Q: 900, K: 0 };
var MATE = 100000;

/* Piece-square tables, white's point of view, row 0 = rank 8 (enemy side) */
var PST = {
  P: [[0,0,0,0,0,0,0,0],[50,50,50,50,50,50,50,50],[10,10,20,30,30,20,10,10],
      [5,5,10,25,25,10,5,5],[0,0,0,20,20,0,0,0],[5,-5,-10,0,0,-10,-5,5],
      [5,10,10,-20,-20,10,10,5],[0,0,0,0,0,0,0,0]],
  N: [[-50,-40,-30,-30,-30,-30,-40,-50],[-40,-20,0,0,0,0,-20,-40],
      [-30,0,10,15,15,10,0,-30],[-30,5,15,20,20,15,5,-30],
      [-30,0,15,20,20,15,0,-30],[-30,5,10,15,15,10,5,-30],
      [-40,-20,0,5,5,0,-20,-40],[-50,-40,-30,-30,-30,-30,-40,-50]],
  B: [[-20,-10,-10,-10,-10,-10,-10,-20],[-10,0,0,0,0,0,0,-10],
      [-10,0,5,10,10,5,0,-10],[-10,5,5,10,10,5,5,-10],
      [-10,0,10,10,10,10,0,-10],[-10,10,10,10,10,10,10,-10],
      [-10,5,0,0,0,0,5,-10],[-20,-10,-10,-10,-10,-10,-10,-20]],
  R: [[0,0,0,0,0,0,0,0],[5,10,10,10,10,10,10,5],[-5,0,0,0,0,0,0,-5],
      [-5,0,0,0,0,0,0,-5],[-5,0,0,0,0,0,0,-5],[-5,0,0,0,0,0,0,-5],
      [-5,0,0,0,0,0,0,-5],[0,0,0,5,5,0,0,0]],
  Q: [[-20,-10,-10,-5,-5,-10,-10,-20],[-10,0,0,0,0,0,0,-10],
      [-10,0,5,5,5,5,0,-10],[-5,0,5,5,5,5,0,-5],
      [0,0,5,5,5,5,0,-5],[-10,5,5,5,5,5,0,-10],
      [-10,0,5,0,0,0,0,-10],[-20,-10,-10,-5,-5,-10,-10,-20]],
  K: [[-30,-40,-40,-50,-50,-40,-40,-30],[-30,-40,-40,-50,-50,-40,-40,-30],
      [-30,-40,-40,-50,-50,-40,-40,-30],[-30,-40,-40,-50,-50,-40,-40,-30],
      [-20,-30,-30,-40,-40,-30,-30,-20],[-10,-20,-20,-20,-20,-20,-20,-10],
      [20,20,0,0,0,0,20,20],[20,30,10,0,0,10,30,20]]
};
var PST_KE = {
  K: [[-50,-40,-30,-20,-20,-30,-40,-50],[-30,-20,-10,0,0,-10,-20,-30],
      [-30,-10,20,30,30,20,-10,-30],[-30,-10,30,40,40,30,-10,-30],
      [-30,-10,30,40,40,30,-10,-30],[-30,-10,20,30,30,20,-10,-30],
      [-30,-30,0,0,0,0,-30,-30],[-50,-30,-30,-30,-30,-30,-30,-50]]
};

function VPos(fen) {
  if (fen) this.setFen(fen); else this.reset();
}
VPos.prototype.reset = function () {
  this.setFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
};
VPos.prototype.setFen = function (fen) {
  var f = fen.trim().split(/\s+/);
  this.board = [];
  var rows = f[0].split("/");
  for (var r = 0; r < 8; r++) {
    var row = [], c = 0, i;
    for (i = 0; i < rows[r].length; i++) {
      var ch = rows[r][i];
      if (ch >= "1" && ch <= "8") { for (var k = 0; k < +ch; k++) row[c++] = "."; }
      else row[c++] = ch;
    }
    this.board.push(row);
  }
  this.turn = (f[1] || "w");
  this.castle = { K: false, Q: false, k: false, q: false };
  var cs = f[2] || "-";
  if (cs.indexOf("K") >= 0) this.castle.K = true;
  if (cs.indexOf("Q") >= 0) this.castle.Q = true;
  if (cs.indexOf("k") >= 0) this.castle.k = true;
  if (cs.indexOf("q") >= 0) this.castle.q = true;
  this.ep = null;
  if (f[3] && f[3] !== "-") {
    this.ep = [8 - +f[3][1], FILES.indexOf(f[3][0])];
  }
  this.halfmove = +(f[4] || 0);
  this.fullmove = +(f[5] || 1);
  this.hist = [];
};
VPos.prototype.fen = function () {
  var rows = [];
  for (var r = 0; r < 8; r++) {
    var s = "", empty = 0;
    for (var c = 0; c < 8; c++) {
      var p = this.board[r][c];
      if (p === ".") empty++;
      else { if (empty) { s += empty; empty = 0; } s += p; }
    }
    if (empty) s += empty;
    rows.push(s);
  }
  var cs = (this.castle.K ? "K" : "") + (this.castle.Q ? "Q" : "") +
           (this.castle.k ? "k" : "") + (this.castle.q ? "q" : "");
  var ep = this.ep ? FILES[this.ep[1]] + (8 - this.ep[0]) : "-";
  return rows.join("/") + " " + this.turn + " " + (cs || "-") + " " + ep +
    " " + this.halfmove + " " + this.fullmove;
};
VPos.prototype.color = function (p) { return p === "." ? null : (p === p.toUpperCase() ? "w" : "b"); };
VPos.prototype.inside = function (r, c) { return r >= 0 && r < 8 && c >= 0 && c < 8; };
VPos.prototype.kingSq = function (side) {
  var k = side === "w" ? "K" : "k";
  for (var r = 0; r < 8; r++) for (var c = 0; c < 8; c++) if (this.board[r][c] === k) return [r, c];
  return null;
};
VPos.prototype.attacked = function (r, c, by) {
  /* FIX: a white attacker-pawn sits one row BELOW the target (r+1),
     a black attacker-pawn one row ABOVE (r-1). */
  var b = this.board, pawn = by === "w" ? "P" : "p", dr = by === "w" ? 1 : -1, d;
  for (d = -1; d <= 1; d += 2) {
    var rr = r + dr, cc = c + d;
    if (this.inside(rr, cc) && b[rr][cc] === pawn) return true;
  }
  var kn = by === "w" ? "N" : "n", J = [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]];
  for (d = 0; d < 8; d++) {
    var rr2 = r + J[d][0], cc2 = c + J[d][1];
    if (this.inside(rr2, cc2) && b[rr2][cc2] === kn) return true;
  }
  var kg = by === "w" ? "K" : "k";
  var a, bb;
  for (a = -1; a <= 1; a++) for (bb = -1; bb <= 1; bb++) {
    if ((a || bb) && this.inside(r + a, c + bb) && b[r + a][c + bb] === kg) return true;
  }
  var rq = by === "w" ? ["R", "Q"] : ["r", "q"], bq = by === "w" ? ["B", "Q"] : ["b", "q"];
  var dirs = [[1,0,rq],[-1,0,rq],[0,1,rq],[0,-1,rq],[1,1,bq],[1,-1,bq],[-1,1,bq],[-1,-1,bq]];
  for (d = 0; d < 8; d++) {
    var dr2 = dirs[d][0], dc = dirs[d][1], set = dirs[d][2];
    var rr3 = r + dr2, cc3 = c + dc;
    while (this.inside(rr3, cc3)) {
      var q = b[rr3][cc3];
      if (q !== ".") { if (set.indexOf(q) >= 0) return true; break; }
      rr3 += dr2; cc3 += dc;
    }
  }
  return false;
};
VPos.prototype.inCheck = function (side) {
  var k = this.kingSq(side);
  return k === null || this.attacked(k[0], k[1], side === "w" ? "b" : "w");
};
/* pseudo-legal moves: [r1,c1,r2,c2,flag,promo] flag: null|ep|castleK|castleQ */
VPos.prototype.pseudo = function (side) {
  var out = [], b = this.board, r, c;
  for (r = 0; r < 8; r++) for (c = 0; c < 8; c++) {
    var p = b[r][c];
    if (p === "." || this.color(p) !== side) continue;
    var P = p.toUpperCase();
    if (P === "P") {
      var d = side === "w" ? -1 : 1, start = side === "w" ? 6 : 1, last = side === "w" ? 0 : 7;
      if (this.inside(r + d, c) && b[r + d][c] === ".") {
        if (r + d === last) out.push([r, c, r + d, c, null, "Q"]);
        else out.push([r, c, r + d, c, null, null]);
        if (r === start && b[r + 2 * d][c] === ".") out.push([r, c, r + 2 * d, c, null, null]);
      }
      for (var dc = -1; dc <= 1; dc += 2) {
        var rr = r + d, cc = c + dc;
        if (!this.inside(rr, cc)) continue;
        var q = b[rr][cc];
        if (q !== "." && this.color(q) !== side) {
          if (rr === last) out.push([r, c, rr, cc, null, "Q"]);
          else out.push([r, c, rr, cc, null, null]);
        }
        if (this.ep && this.ep[0] === rr && this.ep[1] === cc) out.push([r, c, rr, cc, "ep", null]);
      }
    } else if (P === "N") {
      var J = [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]];
      for (var j = 0; j < 8; j++) {
        var nr = r + J[j][0], nc = c + J[j][1];
        if (this.inside(nr, nc) && (b[nr][nc] === "." || this.color(b[nr][nc]) !== side))
          out.push([r, c, nr, nc, null, null]);
      }
    } else if (P === "K") {
      for (var a = -1; a <= 1; a++) for (var bb = -1; bb <= 1; bb++) {
        if (!a && !bb) continue;
        var kr = r + a, kc = c + bb;
        if (this.inside(kr, kc) && (b[kr][kc] === "." || this.color(b[kr][kc]) !== side))
          out.push([r, c, kr, kc, null, null]);
      }
      if (side === "w" && r === 7 && c === 4 && !this.inCheck("w")) {
        if (this.castle.K && b[7][7] === "R" && b[7][5] === "." && b[7][6] === "." &&
            !this.attacked(7, 5, "b") && !this.attacked(7, 6, "b")) out.push([7, 4, 7, 6, "castleK", null]);
        if (this.castle.Q && b[7][0] === "R" && b[7][3] === "." && b[7][2] === "." && b[7][1] === "." &&
            !this.attacked(7, 3, "b") && !this.attacked(7, 2, "b")) out.push([7, 4, 7, 2, "castleQ", null]);
      }
      if (side === "b" && r === 0 && c === 4 && !this.inCheck("b")) {
        if (this.castle.k && b[0][7] === "r" && b[0][5] === "." && b[0][6] === "." &&
            !this.attacked(0, 5, "w") && !this.attacked(0, 6, "w")) out.push([0, 4, 0, 6, "castleK", null]);
        if (this.castle.q && b[0][0] === "r" && b[0][3] === "." && b[0][2] === "." && b[0][1] === "." &&
            !this.attacked(0, 3, "w") && !this.attacked(0, 2, "w")) out.push([0, 4, 0, 2, "castleQ", null]);
      }
    } else {
      var dirs = [];
      if (P === "B" || P === "Q") dirs = dirs.concat([[1,1],[1,-1],[-1,1],[-1,-1]]);
      if (P === "R" || P === "Q") dirs = dirs.concat([[1,0],[-1,0],[0,1],[0,-1]]);
      for (var di = 0; di < dirs.length; di++) {
        var rr2 = r + dirs[di][0], cc2 = c + dirs[di][1];
        while (this.inside(rr2, cc2)) {
          var q2 = b[rr2][cc2];
          if (q2 === ".") out.push([r, c, rr2, cc2, null, null]);
          else {
            if (this.color(q2) !== side) out.push([r, c, rr2, cc2, null, null]);
            break;
          }
          rr2 += dirs[di][0]; cc2 += dirs[di][1];
        }
      }
    }
  }
  return out;
};
VPos.prototype.make = function (m) {
  var b = this.board, r = m[0], c = m[1], rr = m[2], cc = m[3], flag = m[4], promo = m[5];
  var p = b[r][c], captured = b[rr][cc], capSq = [rr, cc];
  if (flag === "ep") { capSq = [p === "P" ? rr + 1 : rr - 1, cc]; captured = b[capSq[0]][capSq[1]]; b[capSq[0]][capSq[1]] = "."; }
  this.hist.push({ m: m, p: p, captured: captured, capSq: capSq,
    castle: { K: this.castle.K, Q: this.castle.Q, k: this.castle.k, q: this.castle.q },
    ep: this.ep ? this.ep.slice() : null, halfmove: this.halfmove, turn: this.turn });
  b[rr][cc] = promo ? (this.turn === "w" ? promo.toUpperCase() : promo.toLowerCase()) : p;
  b[r][c] = ".";
  if (flag === "castleK") { var row = p === "K" ? 7 : 0; b[row][5] = b[row][7]; b[row][7] = "."; }
  else if (flag === "castleQ") { var row2 = p === "K" ? 7 : 0; b[row2][3] = b[row2][0]; b[row2][0] = "."; }
  if (p === "K") { this.castle.K = false; this.castle.Q = false; }
  else if (p === "k") { this.castle.k = false; this.castle.q = false; }
  if (p === "R") { if (r === 7 && c === 0) this.castle.Q = false; if (r === 7 && c === 7) this.castle.K = false; }
  if (p === "r") { if (r === 0 && c === 0) this.castle.q = false; if (r === 0 && c === 7) this.castle.k = false; }
  if (captured === "R") { if (capSq[0] === 7 && capSq[1] === 0) this.castle.Q = false; if (capSq[0] === 7 && capSq[1] === 7) this.castle.K = false; }
  if (captured === "r") { if (capSq[0] === 0 && capSq[1] === 0) this.castle.q = false; if (capSq[0] === 0 && capSq[1] === 7) this.castle.k = false; }
  this.ep = (p.toUpperCase() === "P" && Math.abs(rr - r) === 2) ? [(r + rr) / 2, c] : null;
  this.halfmove = (p.toUpperCase() === "P" || captured !== ".") ? 0 : this.halfmove + 1;
  if (this.turn === "b") this.fullmove++;
  this.turn = this.turn === "w" ? "b" : "w";
};
VPos.prototype.unmake = function () {
  var h = this.hist.pop();
  if (!h) return;
  var b = this.board, m = h.m;
  b[m[0]][m[1]] = h.p;
  b[m[2]][m[3]] = ".";
  if (h.captured !== ".") b[h.capSq[0]][h.capSq[1]] = h.captured;
  if (m[4] === "castleK") { var row = h.p === "K" ? 7 : 0; b[row][7] = b[row][5]; b[row][5] = "."; }
  else if (m[4] === "castleQ") { var row2 = h.p === "K" ? 7 : 0; b[row2][0] = b[row2][3]; b[row2][3] = "."; }
  this.castle = h.castle; this.ep = h.ep; this.halfmove = h.halfmove;
  this.turn = h.turn;
  if (this.turn === "b") this.fullmove--;
};
VPos.prototype.legal = function () {
  var side = this.turn, out = [], i, ms = this.pseudo(side);
  for (i = 0; i < ms.length; i++) {
    var m = ms[i];
    if (this.board[m[2]][m[3]] === (side === "w" ? "k" : "K")) continue;
    this.make(m);
    if (!this.inCheck(side)) out.push(m);
    this.unmake();
  }
  return out;
};
VPos.prototype.insufficient = function () {
  var pieces = [], r, c;
  for (r = 0; r < 8; r++) for (c = 0; c < 8; c++) {
    var p = this.board[r][c];
    if (p !== ".") pieces.push(p.toUpperCase());
  }
  if (pieces.length > 4) return false;
  var nk = pieces.filter(function (p) { return p !== "K"; });
  if (!nk.length) return true;
  if (nk.length === 1 && (nk[0] === "B" || nk[0] === "N")) return true;
  return false;
};
/* ------- evaluation (tapered: middlegame <-> endgame king tables) ------- */
VPos.prototype.phase = function () {
  var npm = 0, r, c;
  for (r = 0; r < 8; r++) for (c = 0; c < 8; c++) {
    var P = this.board[r][c].toUpperCase();
    if (P !== "P" && P !== "K") npm += VAL[P];
  }
  return Math.min(1, npm / 6400); /* 1 = opening, 0 = bare endgame */
};
VPos.prototype.evaluate = function () {
  var score = 0, r, c, b = this.board, ph = this.phase();
  for (r = 0; r < 8; r++) for (c = 0; c < 8; c++) {
    var p = b[r][c];
    if (p === ".") continue;
    var P = p.toUpperCase(), white = p === P;
    var tr = white ? r : 7 - r;
    var pst = (P === "K" && ph < 0.5 ? PST_KE.K : PST[P])[tr][c];
    var v = VAL[P] + pst;
    score += white ? v : -v;
  }
  return this.turn === "w" ? score : -score; /* relative to side to move */
};
/* ------- search ------- */
var abortSearch = false, nodeCount = 0, deadline = 0;
function timeUp() {
  if (abortSearch) return true;
  if ((++nodeCount & 1023) === 0 && Date.now() > deadline) { abortSearch = true; }
  return abortSearch;
}
function moveOrderScore(pos, m) {
  var s = 0;
  var victim = pos.board[m[2]][m[3]];
  if (m[4] === "ep") victim = pos.turn === "w" ? "p" : "P";
  if (victim !== ".") {
    var vv = VAL[victim.toUpperCase()] || 0;
    var av = VAL[pos.board[m[0]][m[1]].toUpperCase()] || 0;
    s += 100000 + vv * 10 - av; /* MVV-LVA */
  }
  if (m[5]) s += 90000;
  return s;
}
function quiesce(pos, alpha, beta, ply) {
  if (timeUp()) return alpha;
  var stand = pos.evaluate();
  if (stand >= beta) return beta;
  if (stand > alpha) alpha = stand;
  if (ply > 24) return alpha;
  var moves = pos.pseudo(pos.turn).filter(function (m) {
    if (pos.board[m[2]][m[3]] !== ".") return true;
    if (m[4] === "ep") return true;
    return !!m[5];
  });
  moves.sort(function (a, b) { return moveOrderScore(pos, b) - moveOrderScore(pos, a); });
  for (var i = 0; i < moves.length; i++) {
    pos.make(moves[i]);
    if (pos.inCheck(pos.turn === "w" ? "b" : "w")) { pos.unmake(); continue; }
    var sc = -quiesce(pos, -beta, -alpha, ply + 1);
    pos.unmake();
    if (abortSearch) return alpha;
    if (sc >= beta) return beta;
    if (sc > alpha) alpha = sc;
  }
  return alpha;
}
function negamax(pos, depth, alpha, beta, ply) {
  if (timeUp()) return alpha;
  if (pos.halfmove >= 100 || pos.insufficient()) return 0;
  var moves = pos.legal();
  if (!moves.length) return pos.inCheck(pos.turn) ? -MATE + ply : 0;
  if (depth <= 0) return quiesce(pos, alpha, beta, ply);
  moves.sort(function (a, b) { return moveOrderScore(pos, b) - moveOrderScore(pos, a); });
  var best = -MATE * 2;
  for (var i = 0; i < moves.length; i++) {
    pos.make(moves[i]);
    var sc = -negamax(pos, depth - 1, -beta, -alpha, ply + 1);
    pos.unmake();
    if (abortSearch) return best > -MATE * 2 ? best : alpha;
    if (sc > best) best = sc;
    if (sc > alpha) alpha = sc;
    if (alpha >= beta) break;
  }
  return best;
}
function uciOf(m) {
  var s = FILES[m[1]] + (8 - m[0]) + FILES[m[3]] + (8 - m[2]);
  if (m[5]) s += m[5].toLowerCase();
  return s;
}
/* root search: returns {uci, score, depth, nodes, time} */
function searchBest(pos, opts) {
  opts = opts || {};
  var maxDepth = Math.max(1, Math.min(64, opts.depth || 64));
  var movetime = Math.max(40, opts.movetime || 800);
  var weakness = Math.max(0, opts.weakness || 0);
  nodeCount = 0; abortSearch = false;
  deadline = Date.now() + movetime;
  var t0 = Date.now();
  var rootMoves = pos.legal();
  if (!rootMoves.length) return { uci: null, score: 0, depth: 0, nodes: 0, time: 0 };
  rootMoves.sort(function (a, b) { return moveOrderScore(pos, b) - moveOrderScore(pos, a); });
  var bestUci = uciOf(rootMoves[0]), bestScore = 0, completed = 0;
  var lastGood = { uci: bestUci, scored: null, depth: 0 };
  for (var d = 1; d <= maxDepth; d++) {
    var scored = [], alpha = -MATE * 2;
    for (var i = 0; i < rootMoves.length; i++) {
      pos.make(rootMoves[i]);
      var sc = -negamax(pos, d - 1, -MATE * 2, -alpha, 1);
      pos.unmake();
      if (abortSearch) break;
      scored.push({ m: rootMoves[i], uci: uciOf(rootMoves[i]), score: sc });
      if (sc > alpha) alpha = sc;
    }
    if (abortSearch) break;
    if (!scored.length) break;
    scored.sort(function (a, b) { return b.score - a.score; });
    bestUci = scored[0].uci; bestScore = scored[0].score;
    completed = d;
    lastGood = { uci: bestUci, scored: scored, depth: d };
    if (typeof opts.onInfo === "function")
      opts.onInfo({ depth: d, score: bestScore, nodes: nodeCount, time: Date.now() - t0, uci: bestUci });
    if (bestScore > MATE - 1000) break; /* mate found */
    if (Date.now() - t0 > movetime * 0.55) break; /* next iteration would not finish */
  }
  var pick = lastGood.uci;
  if (weakness > 0 && lastGood.scored && lastGood.scored.length > 1) {
    var top = lastGood.scored[0].score;
    var pool = lastGood.scored.filter(function (x) { return x.score >= top - weakness; });
    pick = pool[Math.floor(Math.random() * pool.length)].uci;
  }
  return { uci: pick, score: bestScore, depth: completed, nodes: nodeCount,
    time: Date.now() - t0 };
}
/* perft (testing) */
function perft(pos, depth) {
  if (depth === 0) return 1;
  var moves = pos.legal(), n = 0;
  for (var i = 0; i < moves.length; i++) {
    pos.make(moves[i]);
    n += perft(pos, depth - 1);
    pos.unmake();
  }
  return n;
}

var api = { VPos: VPos, searchBest: searchBest, perft: perft, uciOf: uciOf };
if (typeof module !== "undefined" && module.exports) module.exports = api;
else global.VeltrixEngine = api;

/* ------- UCI worker glue (only inside a Web Worker) ------- */
if (typeof importScripts === "function" && typeof self.postMessage === "function") {
  var pos = new VPos();
  var send = function (s) { self.postMessage(s); };
  var opts = { weakness: 0 };
  var parseUciMove = function (u) {
    var ms = pos.legal();
    for (var i = 0; i < ms.length; i++) if (uciOf(ms[i]) === u) return ms[i];
    return null;
  };
  self.onmessage = function (e) {
    var line = String(e.data == null ? "" : e.data).trim();
    if (!line) return;
    var parts = line.split(/\s+/), cmd = parts[0];
    if (cmd === "uci") {
      send("id name Veltrix 1.0 JS Edition");
      send("id author Veltrix Project (amirmhmdglstan-stack)");
      send("option name Weakness type spin default 0 min 0 max 300");
      send("uciok");
    } else if (cmd === "isready") {
      send("readyok");
    } else if (cmd === "ucinewgame") {
      pos = new VPos();
    } else if (cmd === "position") {
      pos = new VPos();
      if (parts[1] === "startpos") {
        pos.reset();
        var mi = parts.indexOf("moves");
        if (mi > 0) for (var i = mi + 1; i < parts.length; i++) {
          var mv = parseUciMove(parts[i]);
          if (mv) pos.make(mv);
        }
      } else if (parts[1] === "fen") {
        var rest = parts.slice(2), mi2 = rest.indexOf("moves");
        var fenParts = mi2 > 0 ? rest.slice(0, mi2) : rest;
        pos.setFen(fenParts.join(" "));
        if (mi2 > 0) for (var k = mi2 + 1; k < rest.length; k++) {
          var mv2 = parseUciMove(rest[k]);
          if (mv2) pos.make(mv2);
        }
      }
    } else if (cmd === "setoption") {
      var ni = parts.indexOf("name"), vi = parts.indexOf("value");
      if (ni >= 0 && vi >= 0) {
        var name = parts.slice(ni + 1, vi).join(" ");
        if (name === "Weakness") opts.weakness = Math.max(0, Math.min(300, +parts[vi + 1] || 0));
      }
    } else if (cmd === "go") {
      var depth = 64, movetime = 900, hasDepth = false;
      for (var g = 1; g < parts.length; g++) {
        if (parts[g] === "depth") { depth = +parts[g + 1] || 64; hasDepth = true; }
        else if (parts[g] === "movetime") movetime = +parts[g + 1] || 900;
        else if (parts[g] === "wtime") movetime = Math.max(80, Math.min(2000, (+parts[g + 1] || 800) / 30));
        else if (parts[g] === "infinite") movetime = 2500;
      }
      if (!hasDepth) depth = 64;
      var res = searchBest(pos, { depth: depth, movetime: movetime, weakness: opts.weakness,
        onInfo: function (nfo) {
          send("info depth " + nfo.depth + " score cp " + nfo.score +
            " nodes " + nfo.nodes + " time " + nfo.time + " pv " + nfo.uci);
        } });
      send(res.uci ? "bestmove " + res.uci : "bestmove (none)");
    } else if (cmd === "stop") {
      /* bounded search; per-move workers make stop unnecessary */
    } else if (cmd === "quit") {
      close();
    }
  };
}
})(typeof self !== "undefined" ? self : globalThis);
