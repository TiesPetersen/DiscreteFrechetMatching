from src.BBMS_core.main import BBMS_core
from src.BBMS_inter.main import BBMS_inter
from src.BBMS_dpp_instant.main import BBMS_dpp_instant
from src.BBMS_dpp_stepwise.main import BBMS_dpp_stepwise
from src.DijkstraPrims.main import DijkstraPrims
from src.DynamicProgramming.main import DynamicProgramming

from src.Point import Point


def main():
    # Example usage of the BBMS algorithm

    # dpp_instant_example
    # curve1 = [Point(11.565934966102509, 17.962498213217646), Point(19.461727009373995, 2.592441227141582), Point(1.6195668155342147, 0.3014014560967615), Point(11.011554944882754, 2.502497718758838), Point(1.0942553211637085, 13.570698120853788), Point(18.097584465792693, 5.809711263037467)]
    # curve2 = [Point(2.074138816090356, 6.727560482110606), Point(3.052311087534252, 17.690106854831672), Point(4.886921695428523, 18.662198049814997), Point(14.846609103129644, 19.138018629340397), Point(16.928442256003216, 8.68376895412503)]

    # .target bug
    curve1 = [Point(19.846487006031847, 9.311782005733276), Point(8.729693296642038, 8.853863284962554), Point(2.9926546755612926, 3.442881302200169), Point(19.400110399965815, 19.300603520584023), Point(0.4741939399868733, 0.11226301122011062), Point(11.427726221561336, 10.280558468737311), Point(2.8550384574120846, 19.172931428064736), Point(13.86412179856104, 12.086793071735723)]
    curve2 = [Point(10.304938981687823, 0.6810881535474733), Point(5.353111327709343, 2.0765791802870393), Point(14.507262102959963, 3.1533927786686067), Point(10.877107962974215, 2.0510409261403084), Point(8.362781681976173, 11.212243633014047), Point(16.17174343471386, 2.3601249137438907), Point(2.7017869203683187, 9.119041361415034), Point(1.5312162050438127, 8.903691612730748), Point(9.581179064296396, 11.223378075705499)]

    # curve1 = [Point(17, 9), Point(9, 0), Point(15, 1), Point(8, 3), Point(17, 8)]
    # curve2 = [Point(18, 17), Point(6, 9), Point(19, 17), Point(3, 2), Point(5, 8), Point(4, 5), Point(2, 4), Point(8, 15)]

    print("BBMS_dpp_instant:")
    matching, distance = BBMS_dpp_instant(curve1, curve2)
    print(f"Discrete Fréchet distance: {distance}")
    print("Matching:" + str(matching))

    # print()

    # print("BBMS_core:")
    # matching, distance = BBMS_core(curve1, curve2)
    # print(f"Discrete Fréchet distance: {distance}")
    # print("Matching:" + str(matching))

    # print()

    # print("BBMS_inter:")
    # matching, distance = BBMS_inter(curve1, curve2)
    # print(f"Discrete Fréchet distance: {distance}")

    # print()

    # print("DijkstraPrims:")
    # matching, distance = DijkstraPrims(curve1, curve2)
    # print(f"Discrete Fréchet distance: {distance}")
    # print("Matching:" + str(matching))

    # print()

    # print("Dynamic Programming:")
    # distance = DynamicProgramming(curve1, curve2)
    # print(f"Discrete Fréchet distance: {distance}")


if __name__ == "__main__":
    main()