import { useReducer, useEffect, useState, type FC, type ReactNode } from "react";
import { PetContext, type PetAction, type PetState } from "./usePet";

const petStateReducer = (state: PetState, action: PetAction): PetState => {
  switch (action.type) {
    case "SET_STATE":
      return action.payload;
    case "IDLE":
      return "idle";
    case "HAPPY":
      return "happy";
    case "THINK":
      return "think";
    case "CURIOUS":
      return "curious";
    case "EXCITE":
      return "excite";
    case "SLEEP":
      return "sleep";
    default:
      return state;
  }
};

interface PetProviderProps {
  children: ReactNode;
}

let lastUserActionTime = Date.now();
const SLEEP_TIMEOUT = 120000; // 2 min idle → sleep

export const PetProvider: FC<PetProviderProps> = ({ children }) => {
  const [state, dispatch] = useReducer(petStateReducer, "idle");
  const [morphId, setMorphId] = useState("rocky");

  // Auto-idle after 3s of state change
  useEffect(() => {
    if (state === "sleep") return;

    const timer = setTimeout(() => {
      const timeSinceLastAction = Date.now() - lastUserActionTime;
      if (timeSinceLastAction < SLEEP_TIMEOUT) {
        dispatch({ type: "IDLE" });
      } else {
        dispatch({ type: "SLEEP" });
      }
    }, 3000);

    return () => clearTimeout(timer);
  }, [state]);

  // Sleep check loop
  useEffect(() => {
    const interval = setInterval(() => {
      const timeSinceLastAction = Date.now() - lastUserActionTime;
      if (timeSinceLastAction >= SLEEP_TIMEOUT && state !== "sleep") {
        dispatch({ type: "SLEEP" });
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [state]);

  const triggerAction = (action: PetAction) => {
    lastUserActionTime = Date.now();
    dispatch(action);
  };

  return (
    <PetContext.Provider value={{ state, dispatch, triggerAction, morphId, setMorphId }}>
      {children}
    </PetContext.Provider>
  );
};
