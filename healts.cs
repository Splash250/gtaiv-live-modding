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
            Ped player = Player.Character;
            if (player == null)
            {
                return;
            }

            player.MakeProofTo(true, true, true, true, true);
            Player.MaxHealth = HealthValue;
            Player.MaxArmor = HealthValue;
            player.Health = HealthValue;
            player.Armor = HealthValue;

            if (player.isInVehicle() && player.CurrentVehicle != null)
            {
                player.CurrentVehicle.MakeProofTo(true, true, true, true, true);
            }
        }
    }
}
