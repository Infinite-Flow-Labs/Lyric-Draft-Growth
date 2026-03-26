# Source Item x-evilcos-06281f365624

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/evilcos/status/2034467033157620111
- Author: evilcos
- Published At: 2026-03-19T03:08:33Z

## Signals
- Release Signals: 
- Task Hints: 
- Fact Anchors: 17

## Content Preview

Post title: SlowMist AI 越来越强了😃

Post summary: SlowMist AI 越来越强了😃 Kong' (@TycheKong) Power by SlowMist AI 👇 **【攻击概览】** - 攻击类型：访问控制缺失（Missing Access Control）导致 LP 池代币被恶意 burn，造成 AMM 价格极端失真后套利 - 受害合约：ShiMama/Shibaba LP 池（`0x564cb2bae0b35cfc8c77d94d65015fe898f8f927`） - 攻击者地址：`0xd10880e7591e30a336b28a5855f0ccb4b8c7c8e9`（EOA） - 攻击合约：`0xcf7380462b7ca3e9f1717d17372eb093bf87f8d5`（在本次交易中动态部署） - 获利金额：约 **52.98 WBNB**（净获利，已扣除 30.78 shimama 代币成本和 gas） --- **【漏洞根本原因】** 合约：`ShiMamaProtocol`（`0x5049d10378356fde0b44c93fa7bb75836f10b49a`） 函数：`executePairBurn(uint256 referenceIn, uint256 minPullFromPair, uint256 deadline)` 缺陷：该函数缺少任何形式的访问控制，任意外部地址均可调用。攻击者可以传入任意大小的 `referenceIn` 参数，配合 `pairBurnBpOnSell = 10000`（100% burn 比例），一次性将 LP 池中几乎全部 shimama 代币强制抽取并 burn 掉，导致 LP 池中 shimama 余额接近于零，AMM 定价机制随之产生极度失真——用极少量 shimama 即可从池中换出大量 shibaba 代币套利。 — https://nitter.net/TycheKong/status/2034464248026595755#m

Canonical URL: https://x.com/evilcos/status/2034467033157620111
