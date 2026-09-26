local addonName, ns = ...

function ns.LoadEvaluationProfile(context)
    if type(context) ~= "table" or not ns.ProfileRepository then
        return nil
    end

    local goal = ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode() or "MYTHIC_PLUS"
    context.goal = goal
    context.specKey = context.specKey
        or (ns.GetStatVerdictSpecKeyBySpecID and ns.GetStatVerdictSpecKeyBySpecID(context.specID))

    ns.ProfileRepository.RefreshProviderView(goal)
    return ns.ProfileRepository.BuildRuntimeProfile(context)
end
