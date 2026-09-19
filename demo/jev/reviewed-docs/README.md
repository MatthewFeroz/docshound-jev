# Two source-reviewed T3Code documentation proposals

These patches were reviewed by the coding agent against T3Code commit
`9cb586acd0494c4f47f60045ee42ef25edb5a07c`. They are distinct from the unedited
Luna drafts preserved in the recording. They are not human benchmark labels or
maintainer-approved changes.

| Issue | Proposed change | Target |
|---|---|---|
| [#9352](https://github.com/pingdotgg/t3code/issues/9352) | Explain how to enable the existing context-window indicator | `docs/user/composer.md` |
| [#12330](https://github.com/pingdotgg/t3code/issues/12330) | Explain GitHub-only change-request template discovery and the manual alternative | `docs/user/source-control.md` |

Source verification:

- [Indicator control](https://github.com/pingdotgg/t3code/blob/9cb586acd0494c4f47f60045ee42ef25edb5a07c/apps/web/src/components/settings/SettingsPanels.tsx#L2065-L2078), [default-off setting](https://github.com/pingdotgg/t3code/blob/9cb586acd0494c4f47f60045ee42ef25edb5a07c/packages/contracts/src/settings.ts#L429), and [composer visibility](https://github.com/pingdotgg/t3code/blob/9cb586acd0494c4f47f60045ee42ef25edb5a07c/apps/web/src/components/chat/ChatComposer.tsx#L6973).
- [GitHub-only template gate](https://github.com/pingdotgg/t3code/blob/9cb586acd0494c4f47f60045ee42ef25edb5a07c/apps/server/src/git/GitManager.ts#L2023-L2026) and [recognized template paths](https://github.com/pingdotgg/t3code/blob/9cb586acd0494c4f47f60045ee42ef25edb5a07c/apps/server/src/sourceControl/PrTemplateDetection.ts#L11-L24).

Both patches passed `git apply --check` against the local checkout at that
commit. They have not been applied or pushed to T3Code. Review against the
current revision before applying, because behavior and documentation can change.

The patches explain current behavior. They do not resolve the requests to make
the indicator default-on or implement additional template providers. The raw
context-indicator draft's misleading proposed-fix "Resolution" section is
intentionally absent from the reviewed patch.
