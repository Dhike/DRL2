import { Suspense } from "react";

import VerifyForm from "../components/VerifyForm";

export default function VerifyPage() {
  return (
    <Suspense fallback={null}>
      <VerifyForm />
    </Suspense>
  );
}
