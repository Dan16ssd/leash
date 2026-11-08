// Leash testnet signer: the only component that holds a key.
// Leash (Python) calls this ONLY after a transaction got ALLOW or owner approval.
//
//   node signer.mjs keygen            create testnet keys in .env (agent + recipient), print addresses
//   node signer.mjs address           print addresses
//   node signer.mjs balance [addr]    print INJ balance
//   echo '{"to_address":"inj1..","denom":"inj","amount":"0.01"}' | node signer.mjs send [--simulate]
//
// Testnet only (chain injective-888). Never put a mainnet key in .env.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { ChainGrpcBankApi, MsgBroadcasterWithPk, MsgSend, PrivateKey } from "@injectivelabs/sdk-ts";
import { Network, getNetworkEndpoints, getNetworkInfo } from "@injectivelabs/networks";
import { BigNumberInBase } from "@injectivelabs/utils";

const NETWORK = Network.Testnet;
const INFO = getNetworkInfo(NETWORK);
const ENDPOINTS = getNetworkEndpoints(NETWORK);
const ENV = join(dirname(fileURLToPath(import.meta.url)), ".env");
const EXPLORER = "https://testnet.explorer.injective.network/transaction/";

// Leash denom -> on-chain denom + decimals (testnet).
const DENOMS = {
  inj: { denom: "inj", decimals: 18 },
};

function loadEnv() {
  if (!existsSync(ENV)) return {};
  return Object.fromEntries(readFileSync(ENV, "utf8").split(/\r?\n/)
    .filter((l) => l.includes("=") && !l.startsWith("#"))
    .map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]));
}

function key(name) {
  const hex = loadEnv()[name];
  if (!hex) throw new Error(`${name} missing in testnet/.env - run: node signer.mjs keygen`);
  return PrivateKey.fromHex(hex);
}

function out(obj) { process.stdout.write(JSON.stringify(obj) + "\n"); }

async function readStdin() {
  let data = "";
  for await (const chunk of process.stdin) data += chunk;
  return JSON.parse(data);
}

async function main() {
  const [cmd, arg] = process.argv.slice(2);

  if (cmd === "keygen") {
    if (existsSync(ENV)) throw new Error("testnet/.env already exists; delete it first to make new keys");
    const agent = PrivateKey.generate().privateKey;
    const recipient = PrivateKey.generate().privateKey;
    writeFileSync(ENV, [
      "# Injective TESTNET keys for the Leash demo. Never use for real funds. Do not commit.",
      `LEASH_AGENT_PK=${agent.toPrivateKeyHex()}`,
      `LEASH_RECIPIENT_PK=${recipient.toPrivateKeyHex()}`,
      "",
    ].join("\n"));
    return out({ agent: agent.toBech32(), recipient: recipient.toBech32(), chain: INFO.chainId });
  }

  if (cmd === "address") {
    return out({ agent: key("LEASH_AGENT_PK").toBech32(), recipient: key("LEASH_RECIPIENT_PK").toBech32() });
  }

  if (cmd === "balance") {
    const addr = arg || key("LEASH_AGENT_PK").toBech32();
    const bal = await new ChainGrpcBankApi(ENDPOINTS.grpc).fetchBalance({ accountAddress: addr, denom: "inj" });
    return out({ address: addr, inj: new BigNumberInBase(bal.amount).toWei(-18).toFixed() });
  }

  if (cmd === "send") {
    const req = await readStdin();
    const d = DENOMS[req.denom];
    if (!d) throw new Error(`denom ${req.denom} not supported on testnet signer yet`);
    if (!/^inj1[0-9a-z]{38}$/.test(req.to_address)) throw new Error("bad recipient address");
    const pk = key("LEASH_AGENT_PK");
    const msg = MsgSend.fromJSON({
      srcInjectiveAddress: pk.toBech32(),
      dstInjectiveAddress: req.to_address,
      amount: { denom: d.denom, amount: new BigNumberInBase(req.amount).toWei(d.decimals).toFixed() },
    });
    const broadcaster = new MsgBroadcasterWithPk({ privateKey: pk, network: NETWORK, simulateTx: true });
    if (arg === "--simulate") {
      const sim = await broadcaster.simulate({ msgs: msg });
      return out({ simulated: true, gas_used: String(sim?.gasInfo?.gasUsed ?? "") });
    }
    const res = await broadcaster.broadcast({ msgs: msg });
    if (res.code) throw new Error(`chain rejected tx (code ${res.code}): ${res.rawLog}`);
    return out({ tx_hash: res.txHash, explorer: EXPLORER + res.txHash, chain: INFO.chainId });
  }

  throw new Error("usage: node signer.mjs keygen|address|balance [addr]|send [--simulate]");
}

main().catch((e) => { out({ error: String(e?.message ?? e) }); process.exit(1); });
