using System;
using GTA;

namespace LiveModding
{
    public class HealtsScript : Script
    {
        private const int HealthValue = 500000;

        public HealtsScript()
        {
            Interval = 250;
            Tick += new EventHandler(OnTick);
            Game.DisplayText("Unlimited health loaded.", 3000);
        }

        private void OnTick(object sender, EventArgs e)
        {
            Player.MaxHealth = HealthValue;
            Player.MaxArmor = HealthValue;
            Player.Character.Health = HealthValue;
            Player.Character.Armor = HealthValue;
        }
    }
}
