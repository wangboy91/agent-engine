const fs = require("fs");
const path = require("path");

const dir = path.join(__dirname, "src", "pages");
for (const f of fs.readdirSync(dir)) {
  if (!f.endsWith(".tsx")) continue;
  const p = path.join(dir, f);
  let s = fs.readFileSync(p, "utf8");
  // repair broken import inserted earlier
  s = s.replace(
    /from "\.\.\/App"`nimport \{ PageShell \} from "\.\.\/components\/PageShell";/g,
    'from "../App";\nimport { PageShell } from "../components/PageShell";',
  );
  if (f === "OverviewPage.tsx") {
    if (!s.includes("components/PageShell")) {
      s = s.replace(
        'import { useApp } from "../App";',
        'import { useApp } from "../App";\nimport { PageShell } from "../components/PageShell";',
      );
    }
    s = s.replace(/function PageShell\(props: \{[\s\S]*?\n\}\n\n/, "");
    s = s.replace(/export \{ PageShell \};\n?/, "");
  } else {
    s = s.replace(
      'import { useApp, PageShell } from "../App";',
      'import { useApp } from "../App";\nimport { PageShell } from "../components/PageShell";',
    );
    if (!s.includes("components/PageShell") && s.includes('from "../App"')) {
      s = s.replace(
        'from "../App";',
        'from "../App";\nimport { PageShell } from "../components/PageShell";',
      );
    }
  }
  fs.writeFileSync(p, s, "utf8");
  console.log("ok", f);
}
