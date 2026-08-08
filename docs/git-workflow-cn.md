# CalmWay Git 操作流程（新手版）

Git 用于管理代码版本。它可以记录项目在不同时间的状态，也可以帮助多位组员安全地协作。

在 CalmWay 项目中，推荐的协作方式是：

```text
main
  → 创建自己的个人分支或功能分支
  → 在自己的分支开发
  → 测试
  → commit
  → push
  → 组员检查
  → 确认无误后合并到 main
```

> **最重要的规则：不要直接在 `main` 上开发。** `main` 应尽量只保存团队已经检查和测试通过的稳定版本。

本文所有命令示例都在 Windows PowerShell 中执行。示例中的仓库地址和分支名需要替换成团队实际使用的值。

## 一、先理解 5 个最基本的 Git 概念

### 1. Repository（仓库）

仓库可以理解为整个项目的 Git 版本管理目录。CalmWay 仓库包含前端、后端、测试、数据占位目录和文档等内容，也包含 Git 用来保存版本历史的信息。

### 2. Branch（分支）

分支可以理解为一条独立的开发线。每位组员可以在自己的分支修改文件，不会立即影响 `main`。

例如，`hongrui` 可以作为个人分支，`feature/sensory-scoring` 可以作为独立功能分支。

### 3. Commit（提交）

commit 可以理解为给当前项目状态保存一个有说明的版本快照。一次 commit 应包含一组相关、已经检查过的修改。

### 4. Push（推送）

push 是把本地电脑中的 commit 上传到 GitHub。只有 commit、没有 push 时，其他组员通常无法在 GitHub 上看到该版本。

### 5. Merge（合并）

merge 是把一个分支中的版本合并到另一个分支。例如，把 `hongrui` 中已经完成的代码合并到 `main`。

还需要理解三个常见词：

- **本地**：自己电脑里的仓库、分支和 commit。
- **远程**：GitHub 上的仓库、分支和 commit。
- **origin**：当前 GitHub 仓库在本地 Git 中通常使用的默认远程名称。

## 二、第一次把 GitHub 项目下载到电脑

第一次参与项目时，在准备存放项目的目录中执行：

```powershell
git clone <repository-url>
```

- **作用**：从 GitHub 下载整个仓库，包括文件和已有 Git 历史。
- **使用时机**：一台电脑第一次获取该项目时使用一次。
- **正常结果**：Terminal 显示正在接收文件，并在当前目录下生成项目文件夹；不应出现 `fatal` 或 `error`。

进入项目目录：

```powershell
cd <repository-folder>
```

- **作用**：让 PowerShell 进入刚刚下载的项目文件夹。
- **使用时机**：执行项目内任何 Git、测试或启动命令之前。
- **正常结果**：PowerShell 当前路径变成项目目录；`cd` 成功时通常没有额外输出。

检查仓库状态：

```powershell
git status
```

- **作用**：查看当前分支、未提交修改、暂存内容以及已知的远程同步状态。
- **使用时机**：刚进入仓库、修改前后、暂存后、提交后和推送后都建议使用。
- **正常结果**：显示类似 `On branch main` 的分支信息；刚 clone 后通常还会显示 `nothing to commit, working tree clean`。

查看本地分支：

```powershell
git branch
```

- **作用**：列出本地已有分支，并标记当前分支。
- **使用时机**：不确定自己在哪个分支，或准备切换分支之前。
- **正常结果**：显示一个或多个分支；当前分支前面带 `*`。

> 第一次 clone 后不要马上在 `main` 中开发。先更新 `main`，再切换或创建自己的分支。

## 三、每天开始开发前应该做什么

先运行 `git status`，确认没有忘记处理的本地修改。如果工作区不是干净状态，不要盲目切换分支或拉取代码；应先确认这些修改属于什么工作。

### 第一步：切换到 main

```powershell
git switch main
```

- **作用**：切换到本地 `main` 主分支。
- **使用时机**：准备获取最新主分支，或准备从最新 `main` 创建新分支时。
- **正常结果**：显示 `Switched to branch 'main'`；如果已经在 `main`，可能显示 `Already on 'main'`。

### 第二步：更新本地 main

```powershell
git pull origin main
```

- **作用**：从 GitHub 的 `origin/main` 获取最新内容，并合并到本地 `main`。
- **使用时机**：开始主要开发工作前，以及准备合并其他分支前。
- **正常结果**：有更新时显示接收和更新信息；没有更新时显示 `Already up to date.`。

### 第三步：切换到自己的已有分支

```powershell
git switch hongrui
```

- **作用**：切换到已经存在的 `hongrui` 本地分支。
- **使用时机**：更新完 `main` 后，回到自己的开发分支继续工作。
- **正常结果**：显示 `Switched to branch 'hongrui'`，或提示已经位于该分支。

如果自己的分支还不存在，可以创建个人分支：

```powershell
git switch -c hongrui
```

也可以创建功能分支：

```powershell
git switch -c feature/sensory-scoring
```

- **作用**：`git switch -c <branch>` 会从当前位置创建新分支，并立即切换过去。
- **使用时机**：开始一条新的个人开发线或一个独立功能时，只需要执行一次。
- **正常结果**：显示 `Switched to a new branch '分支名'`，随后 `git branch` 中该分支前面带 `*`。

> 创建新分支前，最好先确认本地 `main` 已经更新到最新版本。否则新分支可能从旧代码开始。

## 四、怎么确认自己现在在哪个分支

执行：

```powershell
git branch
```

带 `*` 的分支就是当前分支。例如：

```text
* hongrui
  main
```

这表示当前位于 `hongrui` 分支。

也可以执行：

```powershell
git status
```

正常输出可能包含：

```text
On branch hongrui
```

这句话表示当前位于 `hongrui` 分支。两个命令都不会修改文件，可以在不确定状态时安全使用。

## 五、修改文件以后怎么查看发生了什么

首先执行：

```powershell
git status
```

这是日常流程中最常用的命令之一。它可以告诉你：

- 当前位于哪个分支；
- 哪些已跟踪文件被修改；
- 哪些文件是新文件；
- 哪些修改已经进入暂存区；
- 哪些修改还没有暂存；
- 本地分支与上次获取到的远程状态是否同步。

查看尚未暂存的具体修改：

```powershell
git diff
```

- **作用**：逐行显示已经修改、但尚未通过 `git add` 暂存的内容。
- **使用时机**：修改完成后、执行 `git add` 前，用来检查是否有误改或调试内容。
- **正常结果**：有未暂存修改时显示差异；没有此类修改时不输出内容。

查看已经暂存、准备进入下一次 commit 的修改：

```powershell
git diff --staged
```

- **作用**：逐行显示暂存区中的内容。
- **使用时机**：执行 `git add` 后、执行 commit 前，进行最后内容检查。
- **正常结果**：显示即将提交的差异；暂存区为空时不输出内容。

## 六、把修改加入暂存区

把当前目录下所有未忽略修改加入暂存区：

```powershell
git add .
```

- **作用**：把当前目录及子目录中的新文件、修改和删除加入暂存区。
- **使用时机**：确认当前所有相关修改都属于同一次 commit 时。
- **正常结果**：成功时通常没有输出；再次运行 `git status` 后，相关文件出现在 `Changes to be committed` 下。
- **注意**：它可能一次加入很多文件。多人项目中优先考虑按文件或目录暂存，减少误提交。

只暂存一个文件：

```powershell
git add README.md
```

- **作用**：只把 `README.md` 的当前修改加入暂存区。
- **使用时机**：本次 commit 只需要包含该文件，或希望分批组织修改时。
- **正常结果**：成功时通常没有输出；`git status` 显示该文件已暂存。

只暂存一个目录：

```powershell
git add docs/
```

- **作用**：暂存 `docs/` 中所有未忽略的修改。
- **使用时机**：一次修改集中在文档目录时。
- **正常结果**：成功时通常没有输出；`git status` 显示相关文档已暂存。

`git add` 不会上传 GitHub。它只是在告诉 Git：“这些修改准备进入下一次 commit。”

暂存后一定再执行：

```powershell
git status
```

检查是否漏掉应提交文件，以及是否误加入不应提交的文件。

## 七、哪些文件不能提交到 GitHub

结合当前 CalmWay 项目，以下内容通常不应提交：

| 路径 | 原因 |
| --- | --- |
| `node_modules/` | 前端依赖目录体积很大，可以通过 `npm install` 重新生成。 |
| `dist/` | 前端生产构建结果，可以重新执行 build 生成。 |
| `.venv/` | 本地 Python 虚拟环境，不同电脑的环境和路径可能不同。 |
| `__pycache__/` | Python 自动生成的缓存。 |
| `.pytest_cache/` | pytest 自动生成的缓存。 |
| `.env` | 可能包含本地配置或敏感信息。 |
| `.vscode/` | 个人 VS Code 配置，当前项目不要求团队共享。 |

当前项目的 `.gitignore` 用于忽略这些路径。查看包括已忽略文件在内的完整状态：

```powershell
git status --ignored
```

- **作用**：在普通状态信息之外，列出被 Git 忽略的文件和目录。
- **使用时机**：想确认构建目录、依赖目录或环境文件为何没有出现在普通 `git status` 中时。
- **正常结果**：被忽略内容显示在 `Ignored files` 下；此命令不会修改文件。

确认某个路径是否被忽略，以及由哪条规则忽略：

```powershell
git check-ignore -v <path>
```

- **作用**：检查指定路径是否匹配 `.gitignore`，并显示匹配的规则位置。
- **使用时机**：怀疑某个文件应该被忽略，但不确定规则是否生效时。
- **正常结果**：如果路径被忽略，会显示规则文件、行号、规则和路径；如果未被忽略，通常没有输出。

CalmWay 常用检查示例：

```powershell
git check-ignore -v frontend/node_modules
git check-ignore -v frontend/dist
git check-ignore -v backend/.venv
```

这些命令只检查忽略规则，不会删除目录或修改 Git 状态。正常情况下，每个路径都会显示对应的 `.gitignore` 规则。

## 八、创建一次 Commit

> 本节命令是组员日后自行操作的示例。编写本文档时没有实际执行 commit。

暂存并检查完成后，可以执行：

```powershell
git commit -m "Add pedestrian data loader"
```

- **作用**：把暂存区内容保存为一个本地版本，并附上简短说明。
- **使用时机**：一组相关修改完成、测试通过、`git diff --staged` 检查无误后。
- **正常结果**：显示分支名、简短 commit 编号、说明文字以及修改文件数量。该版本此时仍只在本地。

适合 CalmWay 的说明示例：

```powershell
git commit -m "Add pedestrian data loader"
git commit -m "Add sensory scoring logic"
git commit -m "Update route card UI"
git commit -m "Fix frontend validation"
git commit -m "Update Chinese team documentation"
```

以上每条命令都用于提交与说明文字相符的一组已暂存修改，应在相应工作实际完成并测试后使用。正常结果都是生成一个新的本地 commit；不要为了运行示例而重复执行它们。

尽量不要写含义模糊的说明：

```powershell
git commit -m "update"
git commit -m "test"
git commit -m "change"
```

这些命令技术上也能创建 commit，但说明无法让组员理解具体修改，因此不推荐使用。

## 九、Commit 完成以后怎么确认是否成功

执行：

```powershell
git status
```

可能看到：

```text
Your branch is ahead of 'origin/hongrui' by 1 commit.
```

这表示本地 `hongrui` 比上次已知的 GitHub `origin/hongrui` 多 1 个 commit：本地已经 commit，但还没有 push。

也可能看到：

```text
nothing to commit, working tree clean
```

这表示当前工作目录和暂存区没有尚未提交的修改。它不一定表示本地 commit 已经上传，仍需查看前面的分支同步提示。

## 十、把自己的分支上传到 GitHub

> 本节命令是组员日后自行操作的示例。编写本文档时没有实际执行 push。

个人分支第一次上传时：

```powershell
git push -u origin hongrui
```

- **作用**：把本地 `hongrui` 的 commit 上传到 GitHub，并把它与 `origin/hongrui` 建立默认跟踪关系。
- **使用时机**：该分支第一次 push，且本地已经有需要共享的 commit 时。
- **正常结果**：显示上传对象和远程分支信息，并可能出现 `branch 'hongrui' set up to track 'origin/hongrui'`。

建立跟踪关系后，通常可以直接执行：

```powershell
git push
```

- **作用**：把当前分支尚未上传的本地 commit 推送到已关联的远程分支。
- **使用时机**：当前分支已经设置上游分支，并且本地有新 commit 时。
- **正常结果**：有新内容时显示上传进度；没有新内容时显示 `Everything up-to-date`。

之后执行 `git status`，如果看到：

```text
Your branch is up to date with 'origin/hongrui'.
```

表示根据本地当前掌握的远程信息，本地 `hongrui` 与 `origin/hongrui` 已同步。

## 十一、开发过程中 main 更新了怎么办

假设其他组员已经把代码合并到 `main`，而自己的 `hongrui` 分支还在继续开发，可使用简单的 merge 流程：

```powershell
git switch main
git pull origin main
git switch hongrui
git merge main
```

逐步解释：

1. `git switch main`：进入本地 `main`；在准备更新主分支时使用；正常显示已经切换到 `main`。
2. `git pull origin main`：取得并合并 GitHub 最新 `main`；在本地 `main` 工作区干净时使用；正常显示更新内容或 `Already up to date.`。
3. `git switch hongrui`：回到个人分支；更新完 `main` 后使用；正常显示已经切换到 `hongrui`。
4. `git merge main`：把本地最新 `main` 合并进当前 `hongrui`；需要让个人开发基于最新团队代码时使用；无冲突时显示更新摘要或 `Already up to date.`。

如果发生冲突，应停止继续开发并按第十四节处理。

本项目不把 rebase 作为默认流程。对于小型学校项目，merge 更直观，也更容易让 Git 初学者理解历史。

## 十二、自己的代码完成后怎么合并到 main

### 方法 A：本地直接合并

这种方式只适合小型 practice、团队已经人工确认代码没有问题，并且仓库允许直接推送 `main` 的情况。

```powershell
git switch main
git pull origin main
git merge hongrui
git push origin main
git status
```

逐步解释：

1. `git switch main`：切换到接收修改的 `main`；合并前使用；正常显示位于 `main`。
2. `git pull origin main`：确保本地 `main` 是 GitHub 最新版本；合并前使用；正常显示更新或 `Already up to date.`。
3. `git merge hongrui`：把 `hongrui` 的 commit 合并进当前 `main`；只有团队确认和测试通过后才使用；正常显示合并摘要，或提示无需更新。
4. `git push origin main`：把合并后的本地 `main` 上传到 GitHub；仓库规则允许直接推送时使用；正常显示远程更新。若分支受保护，GitHub 可能拒绝该命令，此时应改用 Pull Request。
5. `git status`：确认合并和推送后的状态；最后检查时使用；理想输出如下。

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

逐行含义：

- `On branch main`：当前位于 `main`。
- `Your branch is up to date with 'origin/main'.`：本地 `main` 与上次已知的远程 `origin/main` 同步。
- `nothing to commit, working tree clean`：没有未提交的本地修改。

### 方法 B：GitHub Pull Request

Pull Request 不是 Git 技术上必需的步骤，但更适合：

- 正式团队协作；
- 需要其他组员 review；
- 需要保留审核记录；
- 课程最终项目。

操作流程：

1. 使用第十节方法把个人分支 push 到 GitHub。
2. 打开 GitHub 仓库。
3. 点击 `Pull requests`。
4. 点击 `New pull request`。
5. `base` 选择 `main`。
6. `compare` 选择自己的分支，例如 `hongrui`。
7. 点击 `Create pull request`。
8. 请其他组员检查代码、测试结果和文档。
9. 确认无误后点击 `Merge pull request`。

`base: main` 表示修改最终要进入 `main`；`compare: hongrui` 表示查看 `hongrui` 相对于 `main` 的修改。

CalmWay 的 Part 1A Code Quality Plan 已计划采用 feature branches、Pull Requests 和 peer review，因此最终 assessed work 推荐使用 Pull Request。

## 十三、合并代码之前必须做什么

合并前按顺序检查：

### 1. 查看 Git 状态

```powershell
git status
```

- **作用**：确认分支、暂存区和工作区状态。
- **使用时机**：测试及合并前。
- **正常结果**：位于预期的个人或功能分支，没有意外文件。

### 2. 运行后端测试

在项目根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest
```

- **作用**：使用项目虚拟环境运行后端自动化测试。
- **使用时机**：准备 commit、push 或合并前。
- **正常结果**：当前版本预期显示 `3 passed`，且没有失败测试。

### 3. 运行前端生产构建

```powershell
cd frontend
npm run build
```

- **作用**：进入前端目录并执行 TypeScript 检查及 Vite 生产构建。
- **使用时机**：前端相关修改准备合并前。
- **正常结果**：显示 Vite 构建成功，并且没有 TypeScript errors。

如果 PowerShell 阻止 `npm.ps1`，使用：

```powershell
npm.cmd run build
```

它与 `npm run build` 执行同一个项目脚本，只是避开 PowerShell 脚本执行限制；正常结果相同。

### 4. 手动检查

启动前后端并打开页面，确认本次修改对应的功能正常。可参考 `docs/testing-guide-cn.md`。

### 5. 确认没有本地生成内容被暂存

再次执行 `git status`，确认 `node_modules/`、`dist/`、`.venv/` 和 `.env` 没有被加入 Git。

> 测试没有通过的代码不要合并进 `main`。

## 十四、Merge Conflict 是什么

如果两位组员修改了同一个文件的相同位置，Git 无法自动判断应该保留哪一份内容，就会产生 Merge Conflict（合并冲突）。

发生冲突后执行：

```powershell
git status
```

- **作用**：列出发生冲突的文件和当前合并状态。
- **使用时机**：merge 或 pull 提示 `CONFLICT` 后立即使用。
- **正常结果**：冲突文件显示在 `Unmerged paths` 下；此时不应继续普通开发。

冲突文件中可能出现：

```text
<<<<<<< HEAD
当前分支内容
=======
另一个分支内容
>>>>>>> main
```

- `<<<<<<< HEAD` 到 `=======`：当前分支中的内容。
- `=======` 到 `>>>>>>> main`：正在合入的 `main` 中的内容。
- 这些标记只是帮助定位冲突，最终文件中不能保留它们。

处理步骤：

1. 打开冲突文件。
2. 与修改该文件的相关组员确认应保留哪些内容。
3. 手动整理出正确代码。
4. 删除所有冲突标记。
5. 保存文件。
6. 重新运行相关测试。
7. 标记某个冲突文件已经处理：

```powershell
git add <file>
```

- **作用**：把已解决的文件加入暂存区，让 Git 知道该冲突已经处理。
- **使用时机**：只在确认文件内容正确、冲突标记已删除、测试已完成后。
- **正常结果**：命令通常没有输出；`git status` 不再把该文件列为未合并。

8. 所有冲突解决后完成合并 commit：

```powershell
git commit
```

- **作用**：保存本次冲突解决和合并结果；Git 通常会准备默认合并说明。
- **使用时机**：全部冲突文件已处理并暂存后。
- **正常结果**：Git 可能打开编辑器让你确认说明；保存并关闭后会生成合并 commit。如果不熟悉编辑器，先请组员协助，不要连续尝试未知命令。

> 不要看到冲突就直接删除另一位组员的代码。不确定时，应先与相关组员确认。

## 十五、如果改错了，但还没有 Commit

恢复一个已跟踪文件中尚未暂存的修改：

```powershell
git restore README.md
```

- **作用**：丢弃 `README.md` 尚未暂存的本地修改，恢复到暂存区或最近 commit 的版本。
- **使用时机**：明确确认该文件的本地修改全部不需要时。
- **正常结果**：通常没有输出；被丢弃的修改会消失，`git status` 不再列出该未暂存修改。

恢复所有已跟踪文件中尚未暂存的修改：

```powershell
git restore .
```

- **作用**：丢弃当前目录及子目录中所有已跟踪文件的未暂存修改。
- **使用时机**：只有明确确认这些修改全部不需要时才能使用。
- **正常结果**：通常没有输出；相关未暂存修改会消失。它不会自动恢复未跟踪的新文件，也不会默认清除已经暂存的修改。

> **警告：被 `git restore` 丢弃且没有其他备份的修改可能无法恢复。执行前先运行 `git diff` 并逐项确认。**

本项目的普通流程不推荐 `git reset --hard`，也不推荐 force push。这些操作可能覆盖或丢失本地、远程历史；不理解影响时不要使用。

## 十六、查看 GitHub 远程仓库

查看远程配置：

```powershell
git remote -v
```

- **作用**：列出远程名称及其获取、推送地址。
- **使用时机**：确认当前仓库连接到哪个 GitHub 仓库，或排查远程地址问题时。
- **正常结果**：通常显示两行 `origin`，分别标记 `(fetch)` 和 `(push)`。

只获取最新远程信息：

```powershell
git fetch origin
```

- **作用**：从 GitHub 获取最新分支和 commit 信息，更新本地的远程跟踪记录。
- **使用时机**：想了解远程更新，但暂时不希望直接合并到当前工作分支时。
- **正常结果**：有更新时显示新分支或 commit 范围；没有更新时可能没有输出。它不会像 `git pull` 那样直接合并和修改当前工作文件。

## 十七、查看历史 Commit

简要查看最近提交：

```powershell
git log --oneline
```

- **作用**：每个 commit 用一行显示简短编号和说明。
- **使用时机**：想确认最近提交内容、查找某次修改时。
- **正常结果**：按从新到旧显示 commit；按 `q` 退出分页查看。

以图形方式查看所有分支历史：

```powershell
git log --oneline --decorate --graph --all
```

- **作用**：同时显示 commit、分支标签、合并关系和不同开发线。
- **使用时机**：排查分支关系、merge 历史或某个 commit 位于哪里时。
- **正常结果**：显示由字符线条组成的历史图；按 `q` 退出。这不是每天必须执行的命令。

## 十八、CalmWay 推荐分支方式

### main

保存团队已经测试通过、可以共享的稳定版本。不要直接在这里随意开发。

### 个人分支

例如：

```text
hongrui
```

适合个人日常开发或较小修改。

### 功能分支

例如：

```text
feature/real-pedestrian-data
feature/sensory-scoring
feature/frontend-route-ui
```

适合单独开发一个比较独立的功能，完成和测试后再通过 Pull Request 合并到 `main`。

如果只是小修改，可以继续使用个人分支；如果是独立的大功能，建议从最新 `main` 创建清晰命名的 feature 分支。

## 十九、最推荐的日常 Git 操作流程

```text
开始开发
  → git switch main
  → git pull origin main
  → git switch 自己的分支
  → 必要时 git merge main
  → 修改代码
  → 运行测试
  → git status
  → git diff
  → git add 需要提交的文件
  → git status
  → git diff --staged
  → git commit -m "清晰说明本次修改"
  → git push
  → 组员检查或 Pull Request
  → 合并到 main
  → 再次测试
```

其中：更新 `main` 是为了从团队最新版本开始；在个人分支开发是为了保护主分支；两次 `git status` 和差异检查是为了避免漏交或误交；测试通过后才 commit、push 和合并。各命令的正常输出及使用条件见前面对应章节。

## 二十、完整实例：hongrui 分支

假设个人分支名为 `hongrui`。

### 开始开发

```powershell
git switch main
git pull origin main
git switch hongrui
```

1. `git switch main`：进入主分支；每天更新代码前使用；正常显示已切换到 `main`。
2. `git pull origin main`：更新本地主分支；工作区干净时使用；正常显示更新或 `Already up to date.`。
3. `git switch hongrui`：回到个人分支；准备开发时使用；正常显示已切换到 `hongrui`。

如果 `main` 比 `hongrui` 新，再执行 `git merge main`。它会把最新主分支合入个人分支；需要同步团队更新时使用；无冲突时显示合并摘要。

### 开发和测试完成后

```powershell
git status
git add .
git status
git commit -m "Update CalmWay feature"
git push origin hongrui
```

1. 第一次 `git status`：查看实际修改和当前分支；暂存前使用；正常列出本次修改。
2. `git add .`：暂存全部未忽略修改；只有这些修改都属于本功能时使用；正常情况下没有输出。
3. 第二次 `git status`：复核暂存文件；commit 前使用；目标文件应出现在 `Changes to be committed`。
4. `git commit -m "Update CalmWay feature"`：创建本地版本；检查和测试通过后使用；正常显示新 commit 摘要。实际工作中应把说明改得更具体。
5. `git push origin hongrui`：上传个人分支；需要让组员或 GitHub 看到 commit 时使用；正常显示远程更新。

### 如果团队允许本地合并

```powershell
git switch main
git pull origin main
git merge hongrui
git push origin main
git status
```

这五步依次用于进入主分支、获取最新主分支、合入个人修改、上传合并后的主分支、确认最终状态。只能在测试通过、组员确认且仓库允许直接推送时执行；正常最终状态应显示本地 `main` 与 `origin/main` 同步且工作区干净。正式 assessed work 优先使用 Pull Request。

## 二十一、常见 Git 提示是什么意思

### `On branch hongrui`

当前位于 `hongrui` 分支。

### `Your branch is up to date with 'origin/hongrui'.`

根据本地当前掌握的远程信息，本地 `hongrui` 与 GitHub 上的 `origin/hongrui` 已同步。

### `Your branch is ahead of 'origin/hongrui' by 1 commit.`

本地比远程多 1 个 commit，通常表示已经 commit，但还没有 push。

### `Changes not staged for commit`

有已跟踪文件被修改，但这些修改还没有通过 `git add` 加入暂存区。

### `Changes to be committed`

下面列出的内容已经通过 `git add` 进入暂存区，将进入下一次 commit。

### `Untracked files`

下面列出的是新文件，Git 目前还没有开始跟踪。确认它们是否应该提交，再决定是否执行 `git add`。

### `nothing to commit, working tree clean`

当前没有尚未提交的已跟踪修改，暂存区也是空的。

### `Already up to date.`

当前分支已经包含本次 pull 或 merge 所要引入的最新内容，没有新修改需要合并。

### `CONFLICT`

发生合并冲突，Git 无法自动完成合并，需要人工检查和解决。此时先运行 `git status`，不要继续连续执行其他命令。

## 二十二、常见问题

### Q1：每次写代码之前都必须 git pull 吗？

多人同时开发时，建议开始主要开发前更新一次 `main`，避免自己的工作建立在很旧的版本上。开始前先用 `git status` 确认工作区状态，再按第三节流程更新。

### Q2：可以直接在 main 写代码吗？

不推荐。`main` 应尽量保持稳定，应在个人分支或 feature 分支中开发和测试。

### Q3：为什么 node_modules 没出现在 git status？

因为它已经被 `.gitignore` 忽略，而且可以通过 `npm install` 重新生成，所以不应提交。

### Q4：commit 之后为什么 GitHub 还看不到？

因为 commit 只保存在本地，还需要在正确的个人分支上执行：

```powershell
git push
```

该命令会把当前分支的新 commit 上传到已关联的 GitHub 分支；本地已有未推送 commit 时使用；正常显示上传进度或完成信息。

### Q5：push 和 merge 有什么区别？

- push：把本地分支的 commit 上传到 GitHub 对应的远程分支。
- merge：把两个分支的历史和代码合并。

### Q6：每次都必须 Pull Request 吗？

Git 技术上不是必须。小型 practice 可以在组员确认后直接 merge；最终正式 assessed work 更推荐 Pull Request，因为可以保留 review 记录。

### Q7：为什么经常要运行 git status？

因为它可以帮助避免：

- 在错误分支提交；
- 漏提交文件；
- 提交不应提交的文件；
- 忘记 push；
- 不清楚当前 Git 状态。

## 二十三、提交前最终检查清单

- [ ] 我确认当前所在分支正确
- [ ] 我已经运行 `git status`
- [ ] 我已经运行需要的测试
- [ ] 后端 pytest 已通过
- [ ] 前端 build 已通过
- [ ] `node_modules/` 没有提交
- [ ] `dist/` 没有提交
- [ ] `.venv/` 没有提交
- [ ] `.env` 没有提交
- [ ] `git add` 后重新检查了 `git status`
- [ ] 已用 `git diff --staged` 检查将要提交的内容
- [ ] commit message 能说明本次做了什么
- [ ] 已经 push 到自己的远程分支
- [ ] 合并 `main` 前已经更新本地 `main`
- [ ] merge 后再次检查和测试
- [ ] 最终 `main` 已按团队流程同步到 GitHub

## 二十四、给 Git 新手最重要的几个原则

1. 不确定时先运行 `git status`。它只查看状态，不会修改文件。
2. 不要直接在 `main` 随意开发。
3. 写代码前先更新 `main`。
4. 一组相关功能完成并测试后再 commit。
5. commit 不等于上传 GitHub，还需要 push。
6. 合并之前一定测试。
7. 遇到 conflict 不要乱删代码，应与相关组员确认。
8. 不要提交 `node_modules/`、`.venv/`、`dist/`、`.env`。
9. 不要随意使用 force push。
10. 不要使用自己不理解的破坏性 Git 命令。

> 如果 Git 状态和预期不一致，不要继续连续执行命令。先查看 `git status`，并与组员确认后再处理。
