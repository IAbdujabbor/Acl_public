

#yearly_acl_consumptions_per_month
    monthly_consumptions_per_month = []
    if consumption_option == "Yearly" and home_consumption:
        yearly_consumption = home_consumption
        for month, data in YEARLY_PERCENTAGES.items():
            monthly_value = (yearly_consumption * (data["percent"] / 100))
            monthly_consumptions_per_month.append({
                "month": month,
                "days": data["days"],
                "monthly_consumption": round(monthly_value, 1)
        })
    else:
    # For Daily or if not set, you can fill with zeros or skip
        for month, data in YEARLY_PERCENTAGES.items():
            monthly_consumptions.append({
            "month": month,
            "days": data["days"],
            "monthly_consumption": 0
        })
