import type { ReactNode } from "react";

function App(props: { children: ReactNode }) {
  const { children } = props;
  return children;
}

export default App;
