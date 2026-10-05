/**
 * Test sulle regole di gioco: speranza, anime, soglia.
 *   node --test game/tests/
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { GameState, RULES, STATES } from '../src/objectives.js';

const points = [
  { id: 'a', name: 'Anima A', position: [0, 0, 10], verse: 'verso A', canto: 'I, 1' },
  { id: 'b', name: 'Anima B', position: [5, 0, 4], verse: 'verso B', canto: 'III, 9' },
];
const gate = { position: [0, 1.6, -1.2], radius: 2.6 };

function makeGame() {
  return new GameState({ points, gate, spawn: { position: [0, 2, 44] } });
}

test('la partita comincia dal menu con la speranza piena', () => {
  const game = makeGame();
  assert.equal(game.state, STATES.menu);
  assert.equal(game.hope, RULES.hopeStart);
  assert.equal(game.collected, 0);
  assert.equal(game.allCollected, false);
});

test('il buio consuma la speranza, il fuoco la restituisce', () => {
  const game = makeGame();
  game.start();
  game.update(10, { heat: 0 });
  const darkHope = game.hope;
  assert.ok(darkHope < RULES.hopeStart, 'nel buio la speranza cala');

  const warm = makeGame();
  warm.start();
  warm.update(10, { heat: RULES.warmthFull });
  assert.equal(warm.hope, RULES.hopeMax, 'il calore riporta la speranza al massimo');
});

test('camminare nel fuoco brucia', () => {
  const game = makeGame();
  game.start();
  const before = game.hope;
  game.update(2, { heat: 800, inFire: true });
  assert.ok(game.hope < before - 5, `la speranza cala col fuoco (${game.hope})`);
  assert.ok(game.burning > 0.5);
});

test('a zero speranza si muore e il respawn conserva le anime', () => {
  const game = makeGame();
  game.start();
  game.collect(game.points[0]);
  game.update(400, { heat: 0 });
  assert.equal(game.state, STATES.dead);
  assert.equal(game.hope, 0);
  assert.equal(game.deaths, 1);
  game.reset(true);
  assert.equal(game.state, STATES.playing);
  assert.equal(game.hope, RULES.hopeRespawn);
  assert.equal(game.collected, 1, 'le anime raccolte restano');
});

test('le anime si raccolgono una volta sola e danno speranza', () => {
  const game = makeGame();
  game.start();
  game.hope = 40;
  const poi = game.nearestPoint({ x: 0, y: 0, z: 10.6 }, 2.6);
  assert.equal(poi.id, 'a');
  const collected = game.collect(poi);
  assert.equal(collected.verse, 'verso A');
  assert.ok(game.hope > 40);
  assert.equal(game.collect(poi), null, 'non si raccoglie due volte');
  assert.equal(game.nearestPoint({ x: 0, y: 0, z: 10.6 }, 2.6), null);
  assert.equal(game.collected, 1);
});

test('i battenti restano chiusi finché mancano anime', () => {
  const game = makeGame();
  game.start();
  const atGate = { x: 0, y: 1.6, z: -1.0 };
  assert.equal(game.interactionAt(atGate).kind, 'gate-locked');
  assert.equal(game.beginOpening(), false);
  game.collect(game.points[0]);
  game.collect(game.points[1]);
  assert.equal(game.allCollected, true);
  assert.equal(game.interactionAt(atGate).kind, 'gate-open');
  assert.equal(game.beginOpening(), true);
  assert.equal(game.state, STATES.ending);
  game.update(RULES.openDuration + 0.1, { heat: 0 });
  assert.equal(game.state, STATES.done);
  assert.ok(game.doorsOpen > 0.99);
});

test('la distanza dalla soglia è orizzontale', () => {
  const game = makeGame();
  assert.ok(Math.abs(game.gateDistance({ x: 3, y: 50, z: 2.8 }) - 5) < 1e-6);
});

test('le statistiche contano tempo, passi e anime', () => {
  const game = makeGame();
  game.start();
  game.update(30, { heat: RULES.warmthFull });
  game.distance = 123.4;
  const stats = game.stats();
  assert.equal(Math.round(stats.time), 30);
  assert.equal(stats.distance, 123.4);
  assert.equal(stats.total, 2);
});
